-- Add crawl scope controls to audit jobs.
-- Compatible with PostgreSQL.

ALTER TABLE audit_jobs
  ADD COLUMN IF NOT EXISTS crawl_mode TEXT NOT NULL DEFAULT 'all';

ALTER TABLE audit_jobs
  ADD COLUMN IF NOT EXISTS max_videos_override INT;
