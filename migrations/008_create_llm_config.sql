-- Migration 008: Create llm_config table
-- Module: llm-config-management
-- 租户级 LLM 服务商配置表，每租户一条记录，API Key 加密存储

BEGIN;

CREATE TABLE IF NOT EXISTS llm_config (
    tenant_id VARCHAR(64) PRIMARY KEY,
    provider_name VARCHAR(50) NOT NULL DEFAULT 'openai',
    encrypted_api_key TEXT NOT NULL,
    base_url VARCHAR(512) NOT NULL DEFAULT 'https://api.openai.com/v1',
    model_name VARCHAR(100) NOT NULL DEFAULT 'gpt-3.5-turbo',
    temperature NUMERIC(3,1) NOT NULL DEFAULT 0.7 CHECK (temperature >= 0.0 AND temperature <= 2.0),
    max_tokens INTEGER NOT NULL DEFAULT 2048 CHECK (max_tokens >= 1 AND max_tokens <= 32000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
