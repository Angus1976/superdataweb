-- Baidu Pan API configuration per tenant (admin-managed)
CREATE TABLE IF NOT EXISTS baidu_pan_config (
    tenant_id VARCHAR(64) PRIMARY KEY,
    app_key VARCHAR(255) NOT NULL,
    secret_key VARCHAR(255) NOT NULL,
    app_dir VARCHAR(512) NOT NULL DEFAULT '/apps/SuperInsight',
    redirect_uri VARCHAR(512) NOT NULL DEFAULT 'http://localhost:8011/api/baidu-pan/callback',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
