"""Serializer helpers for API responses."""

from __future__ import annotations

from web.models import AuditJob



def job_to_dict(job: AuditJob) -> dict:
    return {
        "job_id": job.id,
        "client_id": job.client_id,
        "client_name": job.client.name if job.client else "",
        "requested_by": job.requester.email if job.requester else "",
        "channel_url": job.channel_url,
        "channel_id": job.channel_id,
        "channel_name": job.channel_name,
        "crawl_mode": job.crawl_mode,
        "max_videos_override": job.max_videos_override,
        "status": job.status,
        "progress_step": job.progress_step,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "summary": {
            "health_score": job.summary_health_score,
            "high_priority": job.summary_high_priority,
            "medium_priority": job.summary_medium_priority,
            "low_priority": job.summary_low_priority,
            "videos_analyzed": job.videos_analyzed,
        },
    }
