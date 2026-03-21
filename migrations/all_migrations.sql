-- ============================================
-- SuperInsight 全部迁移合并脚本
-- 在 Sealos PostgreSQL 终端一次性执行
-- ============================================

-- 001: client_projects & industry_templates
CREATE TABLE IF NOT EXISTS client_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(50) NOT NULL CHECK (industry IN ('finance', 'ecommerce', 'manufacturing')),
    business_domain TEXT,
    raw_requirements JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_projects_tenant ON client_projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON client_projects(status);

CREATE TABLE IF NOT EXISTS industry_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    industry VARCHAR(50) NOT NULL,
    system_prompt TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    is_builtin BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_templates_industry ON industry_templates(industry);

-- 002: interview_sessions & interview_messages
CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    current_round INT DEFAULT 0,
    max_rounds INT DEFAULT 30,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'terminated')),
    template_id UUID,
    summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON interview_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON interview_sessions(tenant_id);

CREATE TABLE IF NOT EXISTS interview_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sanitized_content TEXT NOT NULL,
    extraction_result JSONB,
    implicit_gaps JSONB,
    round_number INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON interview_messages(session_id);

-- 003: ai_friendly_labels & offline_imports
CREATE TABLE IF NOT EXISTS ai_friendly_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    label_data JSONB NOT NULL,
    quality_score JSONB,
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_labels_project ON ai_friendly_labels(project_id);
CREATE INDEX IF NOT EXISTS idx_labels_tenant ON ai_friendly_labels(tenant_id);

CREATE TABLE IF NOT EXISTS offline_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL CHECK (file_type IN ('xlsx', 'json')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_details JSONB,
    import_data JSONB,
    merged_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_imports_project ON offline_imports(project_id);

-- 004: enterprises, users, refresh_tokens
CREATE TABLE IF NOT EXISTS enterprises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    domain VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprises_code ON enterprises(code);
CREATE INDEX IF NOT EXISTS idx_enterprises_domain ON enterprises(domain);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id),
    role VARCHAR(20) DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    is_active BOOLEAN DEFAULT true,
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_users_enterprise ON users(enterprise_id);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    is_used BOOLEAN DEFAULT false,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- 005: uploaded_files
CREATE TABLE IF NOT EXISTS uploaded_files (
    id VARCHAR(64) PRIMARY KEY,
    original_name VARCHAR(512) NOT NULL,
    stored_path VARCHAR(1024) NOT NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    extension VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    content_type VARCHAR(255) NOT NULL DEFAULT '',
    uploaded_by VARCHAR(255) NOT NULL DEFAULT '',
    tenant_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_tenant ON uploaded_files(tenant_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_category ON uploaded_files(category);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_created ON uploaded_files(created_at DESC);

-- 006: baidu_pan_tokens + uploaded_files columns
CREATE TABLE IF NOT EXISTS baidu_pan_tokens (
    tenant_id VARCHAR(64) PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    baidu_uk BIGINT,
    baidu_name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS baidu_pan_fs_id BIGINT;
ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS baidu_pan_path VARCHAR(1024);

-- 007: baidu_pan_config
CREATE TABLE IF NOT EXISTS baidu_pan_config (
    tenant_id VARCHAR(64) PRIMARY KEY,
    app_key VARCHAR(255) NOT NULL,
    secret_key VARCHAR(255) NOT NULL,
    app_dir VARCHAR(512) NOT NULL DEFAULT '/apps/SuperInsight',
    redirect_uri VARCHAR(512) NOT NULL DEFAULT 'http://localhost:8011/api/baidu-pan/callback',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 008: llm_config
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

-- 009: Seed admin account
INSERT INTO enterprises (name, code, domain, status)
VALUES ('文世间', 'wenshijian', 'wenshijian.com', 'active')
ON CONFLICT (code) DO NOTHING;

INSERT INTO users (email, password_hash, enterprise_id, role, is_active)
SELECT
    'admin@wenshijian.com',
    '$2b$12$PkUOIk5zPBBj5s8DG4ijEuUY8EDJDLNnU1x4DYeZtmpjk4K/06hvS',
    e.id,
    'admin',
    true
FROM enterprises e
WHERE e.code = 'wenshijian'
AND NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'admin@wenshijian.com' AND is_deleted = false
);
