# Youtube Audit MASTER OG

Internal YouTube auditing platform for Brainlabs teams.

- Existing CLI pipeline for one-off audits.
- New Flask coworker web app for request intake, job tracking, and artifact delivery.

## Quick Start (Web App)

1. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
# then fill in YOUTUBE_API_KEY and app settings
```

3. Run the app:

```bash
python3 -m web.app
```

4. Open `http://localhost:8080`

## Quick Start (CLI)

Run a full audit with a single command:

```bash
python3 main.py "https://youtube.com/@channelname"
```

This runs:
1. Fetch channel and video data
2. Analyze long-form + Shorts (2026 module)
3. Export Excel workbook (`.xlsx`)
4. Generate Markdown report

### New Deliverables (Audit Outputs)

- Excel now includes:
  - `Needs Timestamps` tab (long-form videos >2 minutes missing chapter timestamps)
  - `Shorts Audit 2026` tab (separate Shorts score + recommendations)
- Markdown now includes:
  - `Timestamp Coverage Audit` section
  - `Shorts Audit (2026)` section

### `analysis.json` Additions

New top-level keys:
- `shortsHealthScore`
- `shortsRecommendations`
- `timestampAudit`

New module key:
- `analysisModules.shorts2026`

New summary keys:
- `shortsVideos`
- `longFormVideos`
- `shortsHighPriority`
- `shortsMediumPriority`
- `shortsLowPriority`
- `timestampEligibleVideos`
- `timestampMissingVideos`
- `timestampCoveragePercent`

## Web App Capabilities

- Queue new audits from a branded UI
- Track status (`queued`, `running`, `completed`, `failed`)
- View job logs and summary metrics
- Download Excel, Markdown, raw JSON, and analysis JSON artifacts
- Filter and search audit history
- Retention cleanup endpoint for scheduled deletion

## Project Structure

- `main.py`: legacy CLI entrypoint
- `tools/`: deterministic pipeline tools
- `web/`: Flask app (routes, services, templates, static brand tokens)
- `migrations/`: DB schema SQL
- `ops/cloudrun/`: Cloud Run deployment files
- `ops/scheduler/`: Scheduler cleanup config
- `reports/`: archived outputs
- `.tmp/`: intermediate and local artifact storage

## Deployment

See:
- `ops/cloudrun/DEPLOY.md`
- `ops/scheduler/README.md`

---
Built with the Youtube Audit MASTER OG Framework.
