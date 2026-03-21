-- Migration 009: Seed default enterprise and super admin account
-- Email: admin@wenshijian.com
-- Default password: Winsai@2024 (请首次登录后立即修改)

BEGIN;

-- 创建企业
INSERT INTO enterprises (name, code, domain, status)
VALUES ('文世间', 'wenshijian', 'wenshijian.com', 'active')
ON CONFLICT (code) DO NOTHING;

-- 创建超级管理员用户
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

COMMIT;
