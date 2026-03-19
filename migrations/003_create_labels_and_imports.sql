-- Migration 003: Create ai_friendly_labels and offline_imports tables
-- Module: label-construction

BEGIN;

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

COMMIT;
