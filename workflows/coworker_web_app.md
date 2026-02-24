# Coworker Web App Workflow

## Goal
Provide an internal Brainlabs interface for submitting and tracking YouTube audit jobs.

## Core Routes
- `GET /` dashboard
- `GET /audits` history + filtering
- `GET /audits/new` create form
- `POST /audits` submit new job
- `GET /audits/<job_id>` job detail
- `GET /api/audits` JSON list
- `GET /api/audits/<job_id>/status` JSON status
- `GET /api/audits/<job_id>/artifacts/<artifact_type>` signed artifact link
- `POST /internal/tasks/run-audit` worker execution endpoint
- `POST /internal/cleanup` retention cleanup endpoint

## Job Lifecycle
1. User submits request on `/audits/new`.
2. App writes `audit_jobs` row with status `queued`.
3. App enqueues Cloud Task (or local dev thread fallback).
4. Worker endpoint runs pipeline and uploads artifacts.
5. App updates summary metrics and final status.
6. Detail page polls status every 5 seconds.

## Local Development
- Set `USE_CLOUD_TASKS=false`
- Set `USE_GCS=false`
- Keep `ALLOW_INSECURE_INTERNAL=true`
- Use SQLite database via default `.env.example`

## Production Defaults
- `USE_CLOUD_TASKS=true`
- `USE_GCS=true`
- `ALLOW_INSECURE_INTERNAL=false`
- Cloud IAP for authentication
