import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from web.app import create_app
from web.db import SessionLocal
from web.models import AuditArtifact, AuditJob, Client, User


ENV_KEYS = [
    "DATABASE_URL",
    "LOCAL_ARTIFACT_DIR",
    "AUTO_CREATE_SCHEMA",
    "DEV_AUTH_EMAIL",
    "USE_GCS",
    "USE_CLOUD_TASKS",
    "SECRET_KEY",
]


class DeleteAuditRouteTests(unittest.TestCase):
    def setUp(self):
        self.previous_env = {key: os.environ.get(key) for key in ENV_KEYS}
        self.temp_dir = tempfile.TemporaryDirectory()

        db_path = Path(self.temp_dir.name) / "test.db"
        artifact_dir = Path(self.temp_dir.name) / "artifacts"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        os.environ["LOCAL_ARTIFACT_DIR"] = str(artifact_dir)
        os.environ["AUTO_CREATE_SCHEMA"] = "1"
        os.environ["DEV_AUTH_EMAIL"] = "qa@brainlabsdigital.com"
        os.environ["USE_GCS"] = "0"
        os.environ["USE_CLOUD_TASKS"] = "0"
        os.environ["SECRET_KEY"] = "test-secret"

        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        SessionLocal.remove()
        self.temp_dir.cleanup()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _create_job(self, status: str, with_artifact: bool = False):
        db_session = SessionLocal()
        try:
            user = User(email="qa@brainlabsdigital.com", display_name="QA")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            client = Client(name=f"Client {uuid.uuid4()}", created_by=user.id, contact="")
            db_session.add(client)
            db_session.commit()
            db_session.refresh(client)

            job = AuditJob(
                client_id=client.id,
                requested_by=user.id,
                channel_url="https://youtube.com/@example",
                status=status,
                progress_step="Ready",
                expires_at=datetime.utcnow() + timedelta(days=180),
            )
            db_session.add(job)
            db_session.commit()
            db_session.refresh(job)

            artifact_relative_path = None
            if with_artifact:
                artifact_relative_path = f"{job.id}/excel_report.xlsx"
                artifact_path = Path(self.app.config["LOCAL_ARTIFACT_DIR"]) / artifact_relative_path
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text("artifact", encoding="utf-8")

                db_artifact = AuditArtifact(
                    job_id=job.id,
                    artifact_type="excel",
                    gcs_path=artifact_relative_path,
                    size_bytes=artifact_path.stat().st_size,
                )
                db_session.add(db_artifact)
                db_session.commit()

            return job.id, artifact_relative_path
        finally:
            db_session.close()

    def test_dashboard_shows_delete_action(self):
        job_id, _ = self._create_job(status="completed")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"/audits/{job_id}/delete".encode("utf-8"), response.data)
        self.assertIn(b"Delete", response.data)

    def test_delete_audit_removes_job_and_artifacts(self):
        job_id, artifact_relative_path = self._create_job(status="completed", with_artifact=True)
        artifact_path = Path(self.app.config["LOCAL_ARTIFACT_DIR"]) / artifact_relative_path
        self.assertTrue(artifact_path.exists())

        response = self.client.post(f"/audits/{job_id}/delete", data={"next": "/"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers.get("Location", "").endswith("/"))

        db_session = SessionLocal()
        try:
            self.assertIsNone(db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none())
            self.assertEqual(
                db_session.query(AuditArtifact).filter(AuditArtifact.job_id == job_id).count(),
                0,
            )
        finally:
            db_session.close()

        self.assertFalse(artifact_path.exists())

    def test_delete_running_audit_is_blocked(self):
        job_id, _ = self._create_job(status="running")

        response = self.client.post(f"/audits/{job_id}/delete", data={"next": "/"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Running audits cannot be deleted.", response.data)

        db_session = SessionLocal()
        try:
            self.assertIsNotNone(db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none())
        finally:
            db_session.close()


if __name__ == "__main__":
    unittest.main()
