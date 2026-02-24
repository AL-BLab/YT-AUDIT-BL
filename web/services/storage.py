"""Artifact storage abstraction for GCS and local filesystem fallback."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from flask import url_for

try:
    from google.cloud import storage
except Exception:  # pragma: no cover
    storage = None


@dataclass
class StoredArtifact:
    path: str
    size_bytes: int


class ArtifactStorage:
    def __init__(self, app_config):
        self.use_gcs = bool(app_config.get("USE_GCS"))
        self.bucket_name = app_config.get("GCS_BUCKET", "")
        self.local_dir = Path(app_config.get("LOCAL_ARTIFACT_DIR", ".tmp/web_artifacts"))
        self.local_dir.mkdir(parents=True, exist_ok=True)

        self._client = None
        if self.use_gcs and storage is not None and self.bucket_name:
            self._client = storage.Client(project=app_config.get("GOOGLE_CLOUD_PROJECT") or None)

    def upload(self, local_path: str, job_id: str, artifact_type: str) -> StoredArtifact:
        source = Path(local_path)
        if not source.exists():
            raise FileNotFoundError(f"Artifact not found: {source}")

        if self.use_gcs and self._client is not None:
            dest_path = f"audits/{job_id}/{source.name}"
            bucket = self._client.bucket(self.bucket_name)
            blob = bucket.blob(dest_path)
            blob.upload_from_filename(str(source))
            return StoredArtifact(path=dest_path, size_bytes=source.stat().st_size)

        dest_dir = self.local_dir / str(job_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{artifact_type}_{source.name}"
        shutil.copy2(source, dest_file)
        relative = str(dest_file.relative_to(self.local_dir))
        return StoredArtifact(path=relative, size_bytes=dest_file.stat().st_size)

    def signed_download_url(self, artifact, expires_minutes: int = 10) -> str:
        if self.use_gcs and self._client is not None:
            bucket = self._client.bucket(self.bucket_name)
            blob = bucket.blob(artifact.gcs_path)
            return blob.generate_signed_url(version="v4", expiration=timedelta(minutes=expires_minutes), method="GET")

        return url_for("api.download_local_artifact", artifact_id=artifact.id, _external=True)

    def delete(self, artifact_path: str) -> None:
        if self.use_gcs and self._client is not None:
            bucket = self._client.bucket(self.bucket_name)
            blob = bucket.blob(artifact_path)
            blob.delete()
            return

        local_path = self.local_dir / artifact_path
        if local_path.exists():
            local_path.unlink()
