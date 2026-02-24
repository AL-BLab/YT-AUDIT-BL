# Cloud Run Deployment

## 1) Build and push image

```bash
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT_ID/REPO/brainlabs-youtube-audit:latest .
```

## 2) Deploy service

```bash
gcloud run services replace ops/cloudrun/service.yaml --region=us-central1
```

## 3) Configure Cloud Tasks queue

```bash
gcloud tasks queues create audit-jobs --location=us-central1
```

## 4) Configure IAM for task service account
Grant `Cloud Run Invoker` to task runner service account for this Cloud Run service.

## 5) Configure IAP
Restrict app access to Brainlabs Google Workspace group via Cloud IAP policy.
