"""JSON API routes for status polling, filtering, and artifact links."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_file
from sqlalchemy import desc, func

from web.auth import get_authenticated_email
from web.db import SessionLocal
from web.models import AuditArtifact, AuditJob, Client
from web.services.serializers import job_to_dict
from web.services.storage import ArtifactStorage

api_bp = Blueprint("api", __name__)



def _ensure_authenticated():
    if not get_authenticated_email():
        abort(401)



def _apply_filters(query):
    status = request.args.get("status", "").strip()
    client_filter = request.args.get("client", "").strip()
    q = request.args.get("q", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    if status:
        query = query.filter(AuditJob.status == status)
    if client_filter:
        query = query.filter(func.lower(Client.name).contains(client_filter.lower()))
    if q:
        lowered = q.lower()
        query = query.filter(
            func.lower(Client.name).contains(lowered)
            | func.lower(AuditJob.channel_url).contains(lowered)
            | func.lower(AuditJob.channel_name).contains(lowered)
        )
    if start_date:
        try:
            query = query.filter(AuditJob.created_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.fromisoformat(end_date) + timedelta(days=1)
            query = query.filter(AuditJob.created_at < end)
        except ValueError:
            pass

    return query


@api_bp.get("/api/audits")
def list_audits():
    _ensure_authenticated()
    db_session = SessionLocal()
    try:
        query = db_session.query(AuditJob).join(Client, Client.id == AuditJob.client_id)
        query = _apply_filters(query)
        jobs = query.order_by(desc(AuditJob.created_at)).limit(200).all()
        return jsonify({"items": [job_to_dict(job) for job in jobs], "count": len(jobs)})
    finally:
        db_session.close()


@api_bp.get("/api/audits/<job_id>/status")
def audit_status(job_id: str):
    _ensure_authenticated()
    db_session = SessionLocal()
    try:
        job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none()
        if not job:
            abort(404)

        payload = job_to_dict(job)
        payload["artifacts"] = [
            {
                "id": artifact.id,
                "type": artifact.artifact_type,
                "size_bytes": artifact.size_bytes,
                "created_at": artifact.created_at.isoformat(),
            }
            for artifact in sorted(job.artifacts, key=lambda item: item.created_at, reverse=True)
        ]
        payload["log_text"] = job.log_text or ""

        return jsonify(payload)
    finally:
        db_session.close()


@api_bp.get("/api/audits/<job_id>/artifacts/<artifact_type>")
def artifact_signed_url(job_id: str, artifact_type: str):
    _ensure_authenticated()
    db_session = SessionLocal()
    try:
        artifact = (
            db_session.query(AuditArtifact)
            .filter(AuditArtifact.job_id == job_id, AuditArtifact.artifact_type == artifact_type)
            .order_by(desc(AuditArtifact.created_at))
            .first()
        )
        if artifact is None:
            abort(404)

        storage = ArtifactStorage(current_app.config)
        url = storage.signed_download_url(artifact, expires_minutes=10)
        return jsonify({"url": url, "expires_in_seconds": 600})
    finally:
        db_session.close()


@api_bp.get("/api/local-artifacts/<artifact_id>/download")
def download_local_artifact(artifact_id: str):
    _ensure_authenticated()
    db_session = SessionLocal()
    try:
        artifact = db_session.query(AuditArtifact).filter(AuditArtifact.id == artifact_id).one_or_none()
        if artifact is None:
            abort(404)

        base_dir = Path(current_app.config["LOCAL_ARTIFACT_DIR"])
        local_path = base_dir / artifact.gcs_path
        if not local_path.exists():
            abort(404)

        return send_file(local_path, as_attachment=True)
    finally:
        db_session.close()
