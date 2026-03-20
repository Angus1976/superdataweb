-- Baidu Pan OAuth tokens per tenant
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

-- Track which local files have been synced to Baidu Pan
ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS baidu_pan_fs_id BIGINT;
ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS baidu_pan_path VARCHAR(1024);
