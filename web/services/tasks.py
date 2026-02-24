"""Task queue dispatching for cloud and local development fallback."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict

try:
    from google.cloud import tasks_v2
except Exception:  # pragma: no cover
    tasks_v2 = None



def _run_inline_job(app, job_id: str) -> None:
    from web.services.job_executor import execute_audit_job

    with app.app_context():
        execute_audit_job(job_id)



def enqueue_audit_job(app, job_id: str) -> Dict[str, Any]:
    """Queue job in Cloud Tasks, or run async thread in local mode."""
    if app.config.get("USE_CLOUD_TASKS") and tasks_v2 is not None:
        client = tasks_v2.CloudTasksClient()
        queue_name = client.queue_path(
            app.config.get("GOOGLE_CLOUD_PROJECT"),
            app.config.get("TASK_QUEUE_LOCATION"),
            app.config.get("TASK_QUEUE_NAME"),
        )

        payload = json.dumps({"job_id": job_id}).encode("utf-8")
        http_request = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": app.config.get("TASK_HANDLER_URL"),
            "headers": {"Content-Type": "application/json"},
            "body": payload,
        }

        if app.config.get("TASK_SERVICE_ACCOUNT_EMAIL"):
            http_request["oidc_token"] = {
                "service_account_email": app.config.get("TASK_SERVICE_ACCOUNT_EMAIL"),
                "audience": app.config.get("INTERNAL_TASK_AUDIENCE") or app.config.get("TASK_HANDLER_URL"),
            }

        task = {"http_request": http_request}
        response = client.create_task(parent=queue_name, task=task)
        return {"mode": "cloud_tasks", "task_name": response.name}

    thread = threading.Thread(target=_run_inline_job, args=(app, job_id), daemon=True)
    thread.start()
    return {"mode": "local_thread", "task_name": f"thread-{thread.ident}"}



def enqueue_cleanup_job(app) -> Dict[str, Any]:
    """Convenience hook for parity with audit job enqueueing."""
    if app.config.get("USE_CLOUD_TASKS") and tasks_v2 is not None:
        return {"mode": "cloud_tasks", "task_name": "scheduler-managed"}

    from web.services.job_executor import run_retention_cleanup

    thread = threading.Thread(target=lambda: run_retention_cleanup(app), daemon=True)
    thread.start()
    return {"mode": "local_thread", "task_name": f"cleanup-thread-{thread.ident}"}
