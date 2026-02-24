# Scheduler Cleanup Job

Create or update cleanup scheduler job:

```bash
gcloud scheduler jobs create http brainlabs-audit-cleanup \
  --schedule="0 4 * * *" \
  --uri="https://YOUR_CLOUD_RUN_URL/internal/cleanup" \
  --http-method=POST \
  --oidc-service-account-email="SCHEDULER_SA@PROJECT_ID.iam.gserviceaccount.com" \
  --oidc-token-audience="https://YOUR_CLOUD_RUN_URL/internal/cleanup" \
  --location=us-central1
```

This endpoint removes expired jobs/artifacts older than `RETENTION_DAYS`.
