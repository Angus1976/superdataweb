"""Property-based tests for LLMConfigService.

Property 2: API Key 加密往返与掩码显示 — 对任意非空 api_key 字符串，
encrypt_api_key → decrypt_api_key 应返回原始值；mask_api_key 应符合掩码规则。

**Validates: Requirements 1.2**
"""

from __future__ import annotations

import os

from hypothesis import given, settings as h_settings, strategies as st

from src.interview.llm_config_service import LLMConfigService

# Ensure a deterministic encryption key is available for tests
os.environ.setdefault("JWT_SECRET", "test-secret-for-property-tests")

_service = LLMConfigService()


# ---------------------------------------------------------------------------
# Property 2: API Key 加密往返与掩码显示
# ---------------------------------------------------------------------------


class TestApiKeyEncryptionRoundtripAndMask:
    """# Feature: llm-config-management, Property 2: API Key 加密往返与掩码显示

    For any non-empty api_key string:
    - encrypt_api_key then decrypt_api_key returns the original api_key
    - mask_api_key returns first4 + "****" + last4 when len > 8, else "****"

    **Validates: Requirements 1.2**
    """

    @given(api_key=st.text(min_size=1, max_size=200))
    @h_settings(max_examples=100, deadline=None)
    def test_encrypt_decrypt_roundtrip(self, api_key: str) -> None:
        """# Feature: llm-config-management, Property 2: API Key 加密往返与掩码显示

        encrypt_api_key → decrypt_api_key must return the original api_key."""
        encrypted = _service.encrypt_api_key(api_key)
        decrypted = _service.decrypt_api_key(encrypted)
        assert decrypted == api_key

    @given(api_key=st.text(min_size=1, max_size=200))
    @h_settings(max_examples=100, deadline=None)
    def test_mask_format(self, api_key: str) -> None:
        """# Feature: llm-config-management, Property 2: API Key 加密往返与掩码显示

        mask_api_key must return first4 + '****' + last4 when len > 8, else '****'."""
        masked = _service.mask_api_key(api_key)

        if len(api_key) <= 8:
            assert masked == "****"
        else:
            expected = api_key[:4] + "****" + api_key[-4:]
            assert masked == expected


import pytest
from unittest.mock import patch, AsyncMock

from src.interview.llm_models import LLMNotConfiguredError


# ---------------------------------------------------------------------------
# Property 3: 环境变量回退
# ---------------------------------------------------------------------------


class TestEnvVarFallback:
    """# Feature: llm-config-management, Property 3: 环境变量回退

    When DB has no config for a tenant, get_effective_config should fall back
    to environment variables. When env vars are also absent, it should raise
    LLMNotConfiguredError.

    **Validates: Requirements 1.3, 6.2, 6.6**
    """

    @given(
        tenant_id=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        api_key=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
        base_url=st.sampled_from([
            "https://api.openai.com/v1",
            "https://api.deepseek.com/v1",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "https://custom.llm.example.com/v1",
        ]),
        model_name=st.sampled_from(["gpt-3.5-turbo", "gpt-4", "deepseek-chat", "qwen-turbo"]),
        temperature=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        max_tokens=st.integers(min_value=1, max_value=32000),
    )
    @h_settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_fallback_to_env_vars(
        self,
        tenant_id: str,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        """# Feature: llm-config-management, Property 3: 环境变量回退

        When DB has no config for the tenant, get_effective_config must return
        values from environment variables."""
        env_patch = {
            "LLM_API_KEY": api_key,
            "LLM_BASE_URL": base_url,
            "LLM_MODEL_NAME": model_name,
            "LLM_TEMPERATURE": str(temperature),
            "LLM_MAX_TOKENS": str(max_tokens),
        }

        svc = LLMConfigService()
        # Patch get_config_decrypted to return None (no DB config)
        with patch.object(svc, "get_config_decrypted", new_callable=AsyncMock, return_value=None):
            with patch.dict(os.environ, env_patch, clear=False):
                result = await svc.get_effective_config(tenant_id)

        assert result["api_key"] == api_key
        assert result["base_url"] == base_url
        assert result["model_name"] == model_name
        assert result["temperature"] == temperature
        assert result["max_tokens"] == max_tokens
        assert result["provider_name"] == "env"

    @given(
        tenant_id=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    @h_settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_raises_when_no_db_and_no_env(self, tenant_id: str) -> None:
        """# Feature: llm-config-management, Property 3: 环境变量回退

        When DB has no config AND LLM_API_KEY env var is absent,
        get_effective_config must raise LLMNotConfiguredError."""
        svc = LLMConfigService()
        # Remove LLM_API_KEY from env to simulate no env config
        env_overrides = {"LLM_API_KEY": ""}
        with patch.object(svc, "get_config_decrypted", new_callable=AsyncMock, return_value=None):
            with patch.dict(os.environ, env_overrides, clear=False):
                with pytest.raises(LLMNotConfiguredError):
                    await svc.get_effective_config(tenant_id)


# ---------------------------------------------------------------------------
# Property 1: 配置保存/读取往返一致性
# ---------------------------------------------------------------------------

from src.interview.llm_config_service import _llm_config_store
from src.interview.llm_models import LLMConfigRequest


class TestConfigSaveLoadRoundtrip:
    """# Feature: llm-config-management, Property 1: 配置保存/读取往返一致性

    For any valid LLM config and any tenant_id:
    - save_config then get_config returns matching provider_name, base_url,
      model_name, temperature, max_tokens values.
    - The api_key should be returned as masked (matching mask_api_key output).
    - Multiple saves for the same tenant_id result in only the last saved
      values being returned (UPSERT semantics).

    **Validates: Requirements 1.1, 1.4**
    """

    @given(
        tenant_id=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        provider_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
        api_key=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
        base_url=st.sampled_from([
            "https://api.openai.com/v1",
            "https://api.deepseek.com/v1",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "https://custom.llm.example.com/v1",
        ]),
        model_name=st.sampled_from(["gpt-3.5-turbo", "gpt-4", "deepseek-chat", "qwen-turbo"]),
        temperature=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        max_tokens=st.integers(min_value=1, max_value=32000),
    )
    @h_settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_save_then_get_roundtrip(
        self,
        tenant_id: str,
        provider_name: str,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        """# Feature: llm-config-management, Property 1: 配置保存/读取往返一致性

        save_config then get_config must return matching field values,
        with api_key returned as masked."""
        _llm_config_store.clear()

        svc = LLMConfigService()
        req = LLMConfigRequest(
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        await svc.save_config(tenant_id, req)
        result = await svc.get_config(tenant_id)

        assert result.configured is True
        assert result.provider_name == provider_name
        assert result.base_url == base_url
        assert result.model_name == model_name
        assert result.temperature == temperature
        assert result.max_tokens == max_tokens
        assert result.api_key_masked == svc.mask_api_key(api_key)

    @given(
        tenant_id=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        configs=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))),
                st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
                st.sampled_from([
                    "https://api.openai.com/v1",
                    "https://api.deepseek.com/v1",
                ]),
                st.sampled_from(["gpt-3.5-turbo", "gpt-4"]),
                st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
                st.integers(min_value=1, max_value=32000),
            ),
            min_size=2,
            max_size=5,
        ),
    )
    @h_settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_upsert_keeps_last_saved_values(
        self,
        tenant_id: str,
        configs: list,
    ) -> None:
        """# Feature: llm-config-management, Property 1: 配置保存/读取往返一致性

        Multiple saves for the same tenant_id must result in only the last
        saved values being returned (UPSERT semantics)."""
        _llm_config_store.clear()

        svc = LLMConfigService()

        for provider_name, api_key, base_url, model_name, temperature, max_tokens in configs:
            req = LLMConfigRequest(
                provider_name=provider_name,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            await svc.save_config(tenant_id, req)

        last = configs[-1]
        last_provider, last_api_key, last_base_url, last_model, last_temp, last_max = last

        result = await svc.get_config(tenant_id)

        assert result.configured is True
        assert result.provider_name == last_provider
        assert result.base_url == last_base_url
        assert result.model_name == last_model
        assert result.temperature == last_temp
        assert result.max_tokens == last_max
        assert result.api_key_masked == svc.mask_api_key(last_api_key)

        # Verify only one record exists for this tenant
        assert tenant_id in _llm_config_store
