# Migrations

This directory contains SQL migrations for Cloud SQL PostgreSQL deployments.

## Apply migration

```bash
psql "$DATABASE_URL" -f migrations/001_init.sql
psql "$DATABASE_URL" -f migrations/002_add_crawl_controls.sql
```

## Local development note

For local SQLite mode, schema is auto-created on app start when `AUTO_CREATE_SCHEMA=true`.
