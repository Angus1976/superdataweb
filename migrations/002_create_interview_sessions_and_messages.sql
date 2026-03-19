-- Migration 002: Create interview_sessions and interview_messages tables
-- Module: intelligent-interview

BEGIN;

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

COMMIT;
