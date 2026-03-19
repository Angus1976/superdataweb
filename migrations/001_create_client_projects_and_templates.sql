-- Migration 001: Create client_projects and industry_templates tables
-- Module: demand-collection

BEGIN;

-- 客户项目表
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

-- 行业模板表
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

COMMIT;
