"""Tests for the cancel audit route."""

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from web.app import create_app
from web.db import SessionLocal
from web.models import AuditJob, Client, User


ENV_KEYS = [
    "DATABASE_URL",
    "LOCAL_ARTIFACT_DIR",
    "AUTO_CREATE_SCHEMA",
    "DEV_AUTH_EMAIL",
    "USE_GCS",
    "USE_CLOUD_TASKS",
    "SECRET_KEY",
]


class CancelAuditRouteTests(unittest.TestCase):
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

    def _create_job(self, status: str):
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
            return job.id
        finally:
            db_session.close()

    def test_cancel_running_job_marks_as_failed(self):
        """A RUNNING job can be cancelled, setting status to failed."""
        job_id = self._create_job(status="running")

        response = self.client.post(
            f"/audits/{job_id}/cancel",
            data={"next": "/"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"cancelled", response.data.lower())

        db_session = SessionLocal()
        try:
            job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one()
            self.assertEqual(job.status, "failed")
            self.assertEqual(job.progress_step, "Cancelled")
            self.assertIn("Manually cancelled", job.error_message)
            self.assertIsNotNone(job.finished_at)
        finally:
            db_session.close()

    def test_cancel_queued_job_marks_as_failed(self):
        """A QUEUED job can also be cancelled before it starts running."""
        job_id = self._create_job(status="queued")

        response = self.client.post(
            f"/audits/{job_id}/cancel",
            data={"next": "/"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        db_session = SessionLocal()
        try:
            job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one()
            self.assertEqual(job.status, "failed")
        finally:
            db_session.close()

    def test_cancel_completed_job_returns_error(self):
        """Cancelling an already COMPLETED job shows an error flash."""
        job_id = self._create_job(status="completed")

        response = self.client.post(
            f"/audits/{job_id}/cancel",
            data={"next": "/"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Only queued or running audits can be cancelled", response.data)

        db_session = SessionLocal()
        try:
            job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one()
            self.assertEqual(job.status, "completed")  # unchanged
        finally:
            db_session.close()

    def test_cancelled_job_can_then_be_deleted(self):
        """After cancellation the job status is failed, so delete succeeds."""
        job_id = self._create_job(status="running")

        # Cancel first
        self.client.post(f"/audits/{job_id}/cancel", data={"next": "/"})

        # Now delete
        response = self.client.post(
            f"/audits/{job_id}/delete",
            data={"next": "/"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        db_session = SessionLocal()
        try:
            self.assertIsNone(db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none())
        finally:
            db_session.close()

    def test_api_cancel_running_job(self):
        """JSON API cancel endpoint returns 200 and changes status."""
        job_id = self._create_job(status="running")

        response = self.client.post(f"/api/audits/{job_id}/cancel", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "cancelled")

        db_session = SessionLocal()
        try:
            job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one()
            self.assertEqual(job.status, "failed")
        finally:
            db_session.close()

    def test_api_cancel_completed_job_returns_409(self):
        """JSON API returns 409 when trying to cancel a non-running job."""
        job_id = self._create_job(status="completed")

        response = self.client.post(f"/api/audits/{job_id}/cancel", content_type="application/json")
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
