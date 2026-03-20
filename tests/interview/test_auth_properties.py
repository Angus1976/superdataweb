"""Property-based tests for AuthService.

Property 1: JWT 令牌兼容性 — 由 AuthService 签发的 JWT 必须能被现有
InterviewSecurity.get_current_tenant 正确解析并返回 tenant_id。

**Validates: Requirements 4.1, 4.2, 4.4**
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings, strategies as st
from jose import jwt

from src.interview.auth_service import AuthService
from src.interview.config import settings
from src.interview.security import InterviewSecurity

_auth_service = AuthService()
_security = InterviewSecurity()


# ---------------------------------------------------------------------------
# Property 1: JWT 令牌兼容性
# ---------------------------------------------------------------------------


class TestJWTTokenCompatibility:
    """Feature: user-auth-management, Property 1: JWT 令牌兼容性

    Any JWT created by AuthService.create_access_token must be decodable by
    InterviewSecurity.get_current_tenant and return the correct tenant_id.

    **Validates: Requirements 4.1, 4.2, 4.4**
    """

    @given(
        user_id=st.uuids(),
        tenant_id=st.uuids(),
        role=st.sampled_from(["admin", "member"]),
    )
    @h_settings(max_examples=50, deadline=None)
    def test_token_decodable_by_interview_security(self, user_id, tenant_id, role):
        """AuthService tokens must be decodable by InterviewSecurity.get_current_tenant
        and return the correct tenant_id."""
        uid = str(user_id)
        tid = str(tenant_id)

        token = _auth_service.create_access_token(uid, tid, role)
        extracted_tenant = _security.get_current_tenant(token)

        assert extracted_tenant == tid

    @given(
        user_id=st.uuids(),
        tenant_id=st.uuids(),
        role=st.sampled_from(["admin", "member"]),
    )
    @h_settings(max_examples=50, deadline=None)
    def test_token_payload_contains_all_required_claims(self, user_id, tenant_id, role):
        """JWT payload must contain user_id, tenant_id, role, exp, and iat."""
        uid = str(user_id)
        tid = str(tenant_id)

        token = _auth_service.create_access_token(uid, tid, role)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert payload["user_id"] == uid
        assert payload["tenant_id"] == tid
        assert payload["role"] == role
        assert "exp" in payload
        assert "iat" in payload
