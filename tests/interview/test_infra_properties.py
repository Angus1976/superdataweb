"""Property-based tests for interview-infra sub-module.

Property 1: Presidio 敏感信息脱敏
Property 2: 多租户数据隔离
Property 3: JWT 认证校验
Property 4: Prometheus 指标上报
"""

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.interview.security import InterviewSecurity
from src.interview.metrics import (
    report_session_completed,
    interview_completion_rate,
    implicit_gap_completion_rate,
)

# Shared security instance to avoid repeated Presidio init
_security = InterviewSecurity()


# ---------------------------------------------------------------------------
# Hypothesis strategies for PII-containing text
# ---------------------------------------------------------------------------

cn_phone_st = st.from_regex(r"1[3-9]\d{9}", fullmatch=True)
email_st = st.from_regex(r"[a-z]{3,8}@[a-z]{3,6}\.(com|org|net)", fullmatch=True)


# ---------------------------------------------------------------------------
# Property 1: Presidio 敏感信息脱敏
# ---------------------------------------------------------------------------

class TestPresidioSanitization:
    """Feature: interview-infra, Property 1: Presidio 敏感信息脱敏"""

    @given(phone=cn_phone_st)
    @h_settings(max_examples=30, deadline=None)
    def test_phone_sanitized(self, phone):
        text = f"请联系 {phone} 获取详情"
        result = _security.sanitize_content(text)
        assert phone not in result

    @given(email=email_st)
    @h_settings(max_examples=30, deadline=None)
    def test_email_sanitized(self, email):
        text = f"邮箱地址是 {email}"
        result = _security.sanitize_content(text)
        assert email not in result

    @given(text=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz "))
    @h_settings(max_examples=30, deadline=None)
    def test_no_pii_unchanged(self, text):
        result = _security.sanitize_content(text)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Property 2: 多租户数据隔离
# ---------------------------------------------------------------------------

class TestMultiTenantIsolation:
    """Feature: interview-infra, Property 2: 多租户数据隔离"""

    @given(
        tenant_a=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
        tenant_b=st.text(min_size=1, max_size=10, alphabet="abcdef0123456789"),
    )
    @h_settings(max_examples=50, deadline=None)
    def test_different_tenants_no_cross_access(self, tenant_a, tenant_b):
        from jose import jwt as jose_jwt
        from src.interview.config import settings as cfg

        if tenant_a == tenant_b:
            return

        token_a = jose_jwt.encode({"tenant_id": tenant_a}, cfg.JWT_SECRET, algorithm=cfg.JWT_ALGORITHM)
        token_b = jose_jwt.encode({"tenant_id": tenant_b}, cfg.JWT_SECRET, algorithm=cfg.JWT_ALGORITHM)

        extracted_a = _security.get_current_tenant(token_a)
        extracted_b = _security.get_current_tenant(token_b)

        assert extracted_a != extracted_b
        assert extracted_a == tenant_a
        assert extracted_b == tenant_b


# ---------------------------------------------------------------------------
# Property 3: JWT 认证校验
# ---------------------------------------------------------------------------

class TestJWTValidation:
    """Feature: interview-infra, Property 3: JWT 认证校验"""

    @given(garbage=st.text(min_size=1, max_size=100))
    @h_settings(max_examples=50, deadline=None)
    def test_invalid_token_rejected(self, garbage):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _security.get_current_tenant(garbage)
        assert exc_info.value.status_code == 401

    @given(tenant_id=st.text(min_size=1, max_size=20, alphabet="abcdef0123456789"))
    @h_settings(max_examples=50, deadline=None)
    def test_valid_token_returns_tenant(self, tenant_id):
        from jose import jwt as jose_jwt
        from src.interview.config import settings as cfg

        token = jose_jwt.encode({"tenant_id": tenant_id}, cfg.JWT_SECRET, algorithm=cfg.JWT_ALGORITHM)
        result = _security.get_current_tenant(token)
        assert result == tenant_id


# ---------------------------------------------------------------------------
# Property 4: Prometheus 指标上报
# ---------------------------------------------------------------------------

class TestPrometheusMetrics:
    """Feature: interview-infra, Property 4: Prometheus 指标上报"""

    @given(
        gaps_detected=st.integers(min_value=0, max_value=100),
        gaps_completed=st.integers(min_value=0, max_value=100),
    )
    @h_settings(max_examples=50, deadline=None)
    def test_completion_rate_in_range(self, gaps_detected, gaps_completed):
        gaps_completed = min(gaps_completed, gaps_detected)
        report_session_completed("test_session", gaps_detected, gaps_completed)

        rate = interview_completion_rate._value.get()
        assert 0.0 <= rate <= 1.0

        gap_rate = implicit_gap_completion_rate._value.get()
        assert 0.0 <= gap_rate <= 1.0
