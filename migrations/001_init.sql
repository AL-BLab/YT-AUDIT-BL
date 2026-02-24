-- Initial schema for Brainlabs coworker audit app.
-- Compatible with PostgreSQL (Cloud SQL).

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clients (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  contact TEXT NOT NULL DEFAULT '',
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_name_lower ON clients (LOWER(name));

CREATE TABLE IF NOT EXISTS audit_jobs (
  id UUID PRIMARY KEY,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  requested_by UUID NOT NULL REFERENCES users(id),
  channel_url TEXT NOT NULL,
  channel_id TEXT NOT NULL DEFAULT '',
  channel_name TEXT NOT NULL DEFAULT '',
  crawl_mode TEXT NOT NULL DEFAULT 'all',
  max_videos_override INT,
  status TEXT NOT NULL,
  progress_step TEXT NOT NULL DEFAULT 'Queued',
  error_message TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  log_text TEXT NOT NULL DEFAULT '',
  summary_health_score INT,
  summary_high_priority INT,
  summary_medium_priority INT,
  summary_low_priority INT,
  videos_analyzed INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_jobs_status ON audit_jobs (status);
CREATE INDEX IF NOT EXISTS idx_audit_jobs_created_at ON audit_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_jobs_expires_at ON audit_jobs (expires_at);

CREATE TABLE IF NOT EXISTS audit_artifacts (
  id UUID PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES audit_jobs(id) ON DELETE CASCADE,
  artifact_type TEXT NOT NULL,
  gcs_path TEXT NOT NULL,
  size_bytes BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_artifacts_job ON audit_artifacts (job_id);
CREATE INDEX IF NOT EXISTS idx_audit_artifacts_type ON audit_artifacts (artifact_type);
