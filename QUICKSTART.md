# Youtube Audit MASTER OG - Quick Start Guide

## Purpose

Run client-ready YouTube audits via either:
- Coworker web app (recommended for teams)
- CLI pipeline (recommended for direct/scripted use)

---

## Web App (Coworker Workflow)

### Prerequisites
- Python 3.9+
- `.env` configured (copy from `.env.example`)
- YouTube API key in `YOUTUBE_API_KEY`

### Run

```bash
python3 -m pip install -r requirements.txt
python3 -m web.app
```

Open `http://localhost:8080`.

### Main Screens
- `/` Dashboard with KPI cards + recent jobs
- `/audits/new` Create an audit request
- `/audits` Filter/search history
- `/audits/{job_id}` Live status, logs, and artifact downloads

### Deliverables per Job
- Excel report (`audit_report.xlsx`)
- Markdown report (`report.md`)
- Raw data (`raw_data.json`)
- Analysis data (`analysis.json`)

### Included Audit Modules (Current)
- Core long-form audit modules (titles/descriptions, tags, engagement, schedule)
- Timestamp coverage audit:
  - Scope: long-form videos only
  - Eligibility: duration > 2 minutes
  - Output: dedicated `Needs Timestamps` tab + markdown section
- Shorts 2026 audit:
  - Separate Shorts score (`shortsHealthScore`)
  - Detection rule: `<=60s`, or `61-180s` with `#shorts` in title/description
  - Output: dedicated `Shorts Audit 2026` tab + markdown section

---

## CLI (Direct Workflow)

### Command

```bash
python3 main.py "https://youtube.com/@channelname"
```

### What Happens
- Fetch channel/video data
- Analyze channel videos (long-form + Shorts module)
- Export Excel workbook
- Generate markdown summary
- Archive output in `reports/`

---

## Ops Notes

- Production deployment: `ops/cloudrun/DEPLOY.md`
- Retention cleanup scheduler: `ops/scheduler/README.md`
- SQL schema migration: `migrations/001_init.sql`
