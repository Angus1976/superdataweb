-- Uploaded files metadata table
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
