"""Configuration for the Brainlabs coworker audit app."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()



def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    secret_key: str
    database_url: str
    youtube_api_key: str
    max_videos: int
    output_folder: str
    retention_days: int

    use_gcs: bool
    gcs_bucket: str
    gcp_project: str

    use_cloud_tasks: bool
    task_queue_name: str
    task_queue_location: str
    task_handler_url: str
    task_service_account_email: str
    internal_task_audience: str

    iap_audience: str
    dev_auth_email: str
    allow_insecure_internal: bool

    local_artifact_dir: str
    auto_create_schema: bool

    @staticmethod
    def from_env() -> "AppConfig":
        root = Path.cwd()
        default_db_path = root / '.tmp' / 'coworker_audit.db'
        default_db_path.parent.mkdir(parents=True, exist_ok=True)
        default_db = f"sqlite:///{default_db_path}"
        local_artifact_dir = Path(os.getenv("LOCAL_ARTIFACT_DIR", ".tmp/web_artifacts"))
        if not local_artifact_dir.is_absolute():
            local_artifact_dir = root / local_artifact_dir
        local_artifact_dir.mkdir(parents=True, exist_ok=True)

        return AppConfig(
            app_env=os.getenv("APP_ENV", "development"),
            secret_key=os.getenv("SECRET_KEY", "dev-change-me"),
            database_url=os.getenv("DATABASE_URL", default_db),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
            max_videos=int(os.getenv("MAX_VIDEOS", "0")),
            output_folder=os.getenv("OUTPUT_FOLDER", ".tmp/youtube_audits"),
            retention_days=int(os.getenv("RETENTION_DAYS", "180")),
            use_gcs=_env_bool("USE_GCS", False),
            gcs_bucket=os.getenv("GCS_BUCKET", ""),
            gcp_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            use_cloud_tasks=_env_bool("USE_CLOUD_TASKS", False),
            task_queue_name=os.getenv("TASK_QUEUE_NAME", ""),
            task_queue_location=os.getenv("TASK_QUEUE_LOCATION", "us-central1"),
            task_handler_url=os.getenv("TASK_HANDLER_URL", ""),
            task_service_account_email=os.getenv("TASK_SERVICE_ACCOUNT_EMAIL", ""),
            internal_task_audience=os.getenv("INTERNAL_TASK_AUDIENCE", ""),
            iap_audience=os.getenv("IAP_AUDIENCE", ""),
            dev_auth_email=os.getenv("DEV_AUTH_EMAIL", "dev@brainlabsdigital.com"),
            allow_insecure_internal=_env_bool("ALLOW_INSECURE_INTERNAL", True),
            local_artifact_dir=str(local_artifact_dir),
            auto_create_schema=_env_bool("AUTO_CREATE_SCHEMA", True),
        )

    def to_flask_config(self) -> dict:
        return {
            "APP_ENV": self.app_env,
            "SECRET_KEY": self.secret_key,
            "DATABASE_URL": self.database_url,
            "YOUTUBE_API_KEY": self.youtube_api_key,
            "MAX_VIDEOS": self.max_videos,
            "OUTPUT_FOLDER": self.output_folder,
            "RETENTION_DAYS": self.retention_days,
            "USE_GCS": self.use_gcs,
            "GCS_BUCKET": self.gcs_bucket,
            "GOOGLE_CLOUD_PROJECT": self.gcp_project,
            "USE_CLOUD_TASKS": self.use_cloud_tasks,
            "TASK_QUEUE_NAME": self.task_queue_name,
            "TASK_QUEUE_LOCATION": self.task_queue_location,
            "TASK_HANDLER_URL": self.task_handler_url,
            "TASK_SERVICE_ACCOUNT_EMAIL": self.task_service_account_email,
            "INTERNAL_TASK_AUDIENCE": self.internal_task_audience,
            "IAP_AUDIENCE": self.iap_audience,
            "DEV_AUTH_EMAIL": self.dev_auth_email,
            "ALLOW_INSECURE_INTERNAL": self.allow_insecure_internal,
            "LOCAL_ARTIFACT_DIR": self.local_artifact_dir,
            "AUTO_CREATE_SCHEMA": self.auto_create_schema,
        }
