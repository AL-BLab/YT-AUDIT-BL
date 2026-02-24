"""Job execution and retention cleanup workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from flask import current_app

from web.db import SessionLocal
from web.models import AuditArtifact, AuditJob
from web.services.audit_runner import run_audit_pipeline
from web.services.storage import ArtifactStorage



def _append_log(db_session, job: AuditJob, message: str) -> None:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    existing = job.log_text or ""
    job.log_text = existing + f"[{timestamp}] {message}\n"
    db_session.add(job)
    db_session.commit()



def _artifact_records(result: Dict) -> List[Dict[str, str]]:
    return [
        {"artifact_type": "excel", "path": result["excel_path"]},
        {"artifact_type": "markdown", "path": result["markdown_path"]},
        {"artifact_type": "raw", "path": result["raw_data_path"]},
        {"artifact_type": "analysis", "path": result["analysis_path"]},
    ]



def execute_audit_job(job_id: str) -> None:
    """Run full audit pipeline for one queued job."""
    db_session = SessionLocal()
    storage = ArtifactStorage(current_app.config)

    try:
        job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none()
        if job is None:
            return

        job.status = "running"
        job.progress_step = "Starting audit"
        job.started_at = datetime.utcnow()
        job.error_message = ""
        db_session.add(job)
        db_session.commit()

        def logger(message: str) -> None:
            refreshed_job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one()
            refreshed_job.progress_step = message.splitlines()[-1][:255] if message else refreshed_job.progress_step
            _append_log(db_session, refreshed_job, message)

        _append_log(db_session, job, "Job execution started")

        max_videos = int(current_app.config.get("MAX_VIDEOS", 0))
        if job.crawl_mode == "limited" and job.max_videos_override:
            max_videos = int(job.max_videos_override)
            _append_log(db_session, job, f"Crawl mode: limited (top {max_videos})")
        else:
            _append_log(db_session, job, "Crawl mode: all channel videos")

        result = run_audit_pipeline(
            channel_url=job.channel_url,
            output_folder=current_app.config["OUTPUT_FOLDER"],
            api_key=current_app.config["YOUTUBE_API_KEY"],
            max_videos=max_videos,
            logger=logger,
        )

        artifacts = _artifact_records(result)
        for artifact in artifacts:
            stored = storage.upload(artifact["path"], job.id, artifact["artifact_type"])
            db_artifact = AuditArtifact(
                job_id=job.id,
                artifact_type=artifact["artifact_type"],
                gcs_path=stored.path,
                size_bytes=stored.size_bytes,
            )
            db_session.add(db_artifact)

        job.channel_id = result.get("channel_id", "")
        job.channel_name = result.get("channel_name", "")
        summary = result.get("summary", {})
        job.summary_health_score = summary.get("summary_health_score")
        job.summary_high_priority = summary.get("summary_high_priority")
        job.summary_medium_priority = summary.get("summary_medium_priority")
        job.summary_low_priority = summary.get("summary_low_priority")
        job.videos_analyzed = summary.get("videos_analyzed")
        job.status = "completed"
        job.progress_step = "Completed"
        job.finished_at = datetime.utcnow()

        db_session.add(job)
        db_session.commit()
        _append_log(db_session, job, "Job completed successfully")

    except Exception as exc:  # pylint: disable=broad-except
        failed_job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none()
        if failed_job is not None:
            failed_job.status = "failed"
            failed_job.progress_step = "Failed"
            failed_job.error_message = str(exc)
            failed_job.finished_at = datetime.utcnow()
            db_session.add(failed_job)
            db_session.commit()
            _append_log(db_session, failed_job, f"Job failed: {exc}")
    finally:
        db_session.close()



def run_retention_cleanup(app) -> Dict[str, int]:
    """Delete expired jobs and artifacts based on retention expiry."""
    with app.app_context():
        db_session = SessionLocal()
        storage = ArtifactStorage(current_app.config)

        deleted_jobs = 0
        deleted_artifacts = 0

        try:
            now = datetime.utcnow()
            expired_jobs = db_session.query(AuditJob).filter(AuditJob.expires_at < now).all()

            for job in expired_jobs:
                for artifact in job.artifacts:
                    storage.delete(artifact.gcs_path)
                    deleted_artifacts += 1
                db_session.delete(job)
                deleted_jobs += 1

            db_session.commit()
            return {"deleted_jobs": deleted_jobs, "deleted_artifacts": deleted_artifacts}
        finally:
            db_session.close()
