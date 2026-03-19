"""Interview module security layer.

Provides JWT authentication, Presidio PII sanitization, and multi-tenant
data isolation for all interview-related APIs.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from jose import JWTError, jwt
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from sqlalchemy import text

from src.interview.config import settings
from src.interview.db import async_session_factory

# PII entity types to detect
_PII_ENTITIES = [
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "PERSON",
    "IBAN_CODE",
    "IP_ADDRESS",
    # Custom Chinese PII types
    "CN_PHONE",
    "CN_ID_CARD",
    "CN_BANK_CARD",
]


def _build_analyzer() -> AnalyzerEngine:
    """Build an AnalyzerEngine with custom Chinese PII recognizers."""
    analyzer = AnalyzerEngine()

    # Chinese mobile phone: 1[3-9]X XXXX XXXX (11 digits)
    cn_phone = PatternRecognizer(
        supported_entity="CN_PHONE",
        name="cn_phone_recognizer",
        patterns=[
            Pattern(
                name="cn_mobile",
                regex=r"(?<!\d)1[3-9]\d{9}(?!\d)",
                score=0.9,
            ),
        ],
        supported_language="en",
    )

    # Chinese national ID card: 18 digits (last may be X)
    cn_id_card = PatternRecognizer(
        supported_entity="CN_ID_CARD",
        name="cn_id_card_recognizer",
        patterns=[
            Pattern(
                name="cn_id",
                regex=r"(?<!\d)\d{17}[\dXx](?!\d)",
                score=0.85,
            ),
        ],
        supported_language="en",
    )

    # Chinese bank card: 16-19 digits
    cn_bank_card = PatternRecognizer(
        supported_entity="CN_BANK_CARD",
        name="cn_bank_card_recognizer",
        patterns=[
            Pattern(
                name="cn_bank",
                regex=r"(?<!\d)\d{16,19}(?!\d)",
                score=0.6,
            ),
        ],
        supported_language="en",
    )

    analyzer.registry.add_recognizer(cn_phone)
    analyzer.registry.add_recognizer(cn_id_card)
    analyzer.registry.add_recognizer(cn_bank_card)

    return analyzer


class InterviewSecurity:
    """访谈模块安全层，复用现有 JWT 机制，集成 Presidio 脱敏。"""

    def __init__(self) -> None:
        self.analyzer = _build_analyzer()
        self.anonymizer = AnonymizerEngine()

    async def verify_tenant_access(self, tenant_id: str, project_id: str) -> bool:
        """校验租户是否有权访问指定项目。

        Queries the ``client_projects`` table to check whether *project_id*
        belongs to *tenant_id*.  Returns ``False`` when the tenant does not
        own the project (caller should return HTTP 403).
        """
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT 1 FROM client_projects "
                    "WHERE project_id = :project_id AND tenant_id = :tenant_id "
                    "LIMIT 1"
                ),
                {"project_id": project_id, "tenant_id": tenant_id},
            )
            return result.scalar() is not None

    def sanitize_content(self, content: str) -> str:
        """使用 Presidio 对文本进行敏感信息去标识化。

        Detects PII entities (phone numbers, ID numbers, emails, credit card
        numbers, person names, etc.) and replaces them with type-based
        placeholders such as ``<PHONE_NUMBER>``.
        """
        all_results = []
        try:
            results = self.analyzer.analyze(
                text=content,
                language="en",
                entities=_PII_ENTITIES,
            )
            all_results.extend(results)
        except Exception:
            pass

        if not all_results:
            return content

        # De-duplicate overlapping detections – keep highest score.
        all_results = _deduplicate(all_results)

        anonymized = self.anonymizer.anonymize(
            text=content,
            analyzer_results=all_results,
        )
        return anonymized.text

    def get_current_tenant(self, token: str) -> str:
        """从 JWT token 中提取 tenant_id。

        Decodes the token using the configured secret and algorithm, then
        returns the ``tenant_id`` claim.  Raises an HTTP 401 exception when
        the token is invalid or the claim is missing.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc

        tenant_id: str | None = payload.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing tenant_id claim",
            )
        return tenant_id


def _deduplicate(results: list) -> list:
    """Remove overlapping analyzer results, keeping the highest score."""
    results.sort(key=lambda r: (r.start, -r.score))
    deduped: list = []
    for r in results:
        if deduped and r.start < deduped[-1].end:
            # Overlapping – keep the one already in deduped (higher score).
            continue
        deduped.append(r)
    return deduped
