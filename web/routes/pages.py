"""HTML page routes for the coworker audit app."""

from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for, abort
from sqlalchemy import desc, func

from web.auth import get_authenticated_email, get_or_create_user
from web.db import SessionLocal
from web.models import AuditJob, Client
from web.services.audit_runner import validate_channel_url
from web.services.storage import ArtifactStorage
from web.services.tasks import enqueue_audit_job

pages_bp = Blueprint("pages", __name__)



def _load_user(db_session):
    email = get_authenticated_email()
    if not email:
        abort(401)
    user = get_or_create_user(db_session, email)
    g.current_user = user
    return user



def _apply_job_filters(query):
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
        q_lower = q.lower()
        query = query.filter(
            func.lower(AuditJob.channel_url).contains(q_lower)
            | func.lower(AuditJob.channel_name).contains(q_lower)
            | func.lower(Client.name).contains(q_lower)
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


def _safe_next_path(default_endpoint: str) -> str:
    next_path = request.form.get("next", "").strip() or request.args.get("next", "").strip()
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return url_for(default_endpoint)


@pages_bp.get("/")
def dashboard():
    db_session = SessionLocal()
    try:
        _load_user(db_session)

        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        base_query = db_session.query(AuditJob)

        stats = {
            "queued": base_query.filter(AuditJob.status == "queued").count(),
            "running": base_query.filter(AuditJob.status == "running").count(),
            "failed": base_query.filter(AuditJob.status == "failed").count(),
            "completed_recent": base_query.filter(
                AuditJob.status == "completed", AuditJob.created_at >= seven_days_ago
            ).count(),
        }

        recent_jobs = (
            db_session.query(AuditJob)
            .join(Client, Client.id == AuditJob.client_id)
            .order_by(desc(AuditJob.created_at))
            .limit(15)
            .all()
        )

        return render_template("dashboard.html", stats=stats, recent_jobs=recent_jobs)
    finally:
        db_session.close()


@pages_bp.get("/audits")
def audits_list():
    db_session = SessionLocal()
    try:
        _load_user(db_session)
        query = db_session.query(AuditJob).join(Client, Client.id == AuditJob.client_id)
        query = _apply_job_filters(query)
        jobs = query.order_by(desc(AuditJob.created_at)).limit(200).all()
        return render_template("audits_list.html", jobs=jobs)
    finally:
        db_session.close()


@pages_bp.get("/audits/new")
def new_audit_form():
    db_session = SessionLocal()
    try:
        _load_user(db_session)
        return render_template("audit_new.html")
    finally:
        db_session.close()


@pages_bp.post("/audits")
def create_audit():
    db_session = SessionLocal()
    try:
        user = _load_user(db_session)

        client_name = request.form.get("client_name", "").strip()
        client_contact = request.form.get("client_contact", "").strip()
        channel_url = request.form.get("channel_url", "").strip()
        notes = request.form.get("notes", "").strip()
        crawl_scope = request.form.get("crawl_scope", "").strip().lower()
        limit_crawl_flag = request.form.get("limit_crawl", "").strip().lower()
        max_videos_raw = request.form.get("max_videos", "").strip()

        if not crawl_scope:
            crawl_scope = "limited" if limit_crawl_flag in {"1", "true", "on", "yes"} else "all"

        if not client_name:
            flash("Client name is required.", "error")
            return redirect(url_for("pages.new_audit_form"))

        if not validate_channel_url(channel_url):
            flash("Invalid YouTube channel URL. Use https://youtube.com/@name or equivalent channel URL.", "error")
            return redirect(url_for("pages.new_audit_form"))

        if crawl_scope not in {"all", "limited"}:
            flash("Invalid crawl scope selection.", "error")
            return redirect(url_for("pages.new_audit_form"))

        max_videos_override = None
        if crawl_scope == "limited":
            try:
                max_videos_override = int(max_videos_raw or "50")
            except ValueError:
                flash("Max videos must be a number.", "error")
                return redirect(url_for("pages.new_audit_form"))
            if max_videos_override <= 0 or max_videos_override > 5000:
                flash("Max videos must be between 1 and 5000.", "error")
                return redirect(url_for("pages.new_audit_form"))

        client = db_session.query(Client).filter(func.lower(Client.name) == client_name.lower()).one_or_none()
        if client is None:
            client = Client(name=client_name, contact=client_contact, created_by=user.id)
            db_session.add(client)
            db_session.commit()
            db_session.refresh(client)
        elif client_contact and client.contact != client_contact:
            client.contact = client_contact
            db_session.add(client)
            db_session.commit()

        job = AuditJob(
            client_id=client.id,
            requested_by=user.id,
            channel_url=channel_url,
            crawl_mode=crawl_scope,
            max_videos_override=max_videos_override,
            status="queued",
            progress_step="Queued",
            notes=notes,
            expires_at=datetime.utcnow() + timedelta(days=int(current_app.config["RETENTION_DAYS"])),
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        enqueue_info = enqueue_audit_job(current_app._get_current_object(), job.id)
        job.progress_step = f"Queued ({enqueue_info.get('mode')})"
        db_session.add(job)
        db_session.commit()

        flash("Audit job created and queued.", "success")
        return redirect(url_for("pages.audit_detail", job_id=job.id))
    finally:
        db_session.close()


@pages_bp.get("/audits/<job_id>")
def audit_detail(job_id: str):
    db_session = SessionLocal()
    try:
        _load_user(db_session)
        job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none()
        if not job:
            abort(404)
        return render_template("audit_detail.html", job=job)
    finally:
        db_session.close()


@pages_bp.get("/audits/<job_id>/logs")
def audit_logs_partial(job_id: str):
    db_session = SessionLocal()
    try:
        _load_user(db_session)
        job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none()
        if not job:
            abort(404)
        return render_template("partials/job_logs.html", job=job)
    finally:
        db_session.close()


@pages_bp.post("/audits/<job_id>/delete")
def delete_audit(job_id: str):
    db_session = SessionLocal()
    storage = ArtifactStorage(current_app.config)
    redirect_target = url_for("pages.dashboard")

    try:
        _load_user(db_session)
        redirect_target = _safe_next_path("pages.dashboard")

        job = db_session.query(AuditJob).filter(AuditJob.id == job_id).one_or_none()
        if job is None:
            flash("Audit job not found.", "error")
            return redirect(redirect_target)

        if job.status == "running":
            flash("Running audits cannot be deleted.", "error")
            return redirect(redirect_target)

        deleted_artifacts = 0
        for artifact in list(job.artifacts):
            try:
                storage.delete(artifact.gcs_path)
                deleted_artifacts += 1
            except FileNotFoundError:
                continue
            except Exception as exc:  # pylint: disable=broad-except
                current_app.logger.warning(
                    "Artifact delete failed for %s (%s): %s",
                    artifact.id,
                    artifact.gcs_path,
                    exc,
                )

        db_session.delete(job)
        db_session.commit()
        flash(f"Audit deleted ({deleted_artifacts} artifact(s) removed).", "success")
        return redirect(redirect_target)
    finally:
        db_session.close()
