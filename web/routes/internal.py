"""Internal endpoints for worker execution and retention cleanup."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from web.services.job_executor import execute_audit_job, run_retention_cleanup
from web.services.security import verify_internal_request

internal_bp = Blueprint("internal", __name__)


@internal_bp.post("/internal/tasks/run-audit")
def run_audit_task():
    ok, reason = verify_internal_request()
    if not ok:
        return jsonify({"error": reason}), 403

    payload = request.get_json(silent=True) or {}
    job_id = payload.get("job_id")
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    execute_audit_job(str(job_id))
    return jsonify({"status": "processed", "job_id": job_id})


@internal_bp.post("/internal/cleanup")
def cleanup_retention():
    ok, reason = verify_internal_request()
    if not ok:
        return jsonify({"error": reason}), 403

    result = run_retention_cleanup(current_app._get_current_object())
    return jsonify({"status": "ok", **result})
