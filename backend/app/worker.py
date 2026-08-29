from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from .config import Settings
from .database import SessionLocal
from .models import JobModel, WebhookEventModel
from .services import audit, mark_webhook_enrichment_failed, process_webhook_event


def claim_and_process_one(settings: Settings) -> bool:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        job = db.scalar(
            select(JobModel)
            .where(
                or_(
                    JobModel.status == "pending",
                    (JobModel.status == "running") & (JobModel.lease_until < now),
                )
            )
            .order_by(JobModel.created_at)
        )
        if not job:
            return False
        job.status = "running"
        job.attempts += 1
        job.lease_until = now + timedelta(seconds=settings.job_lease_seconds)
        db.commit()
        job_id = job.id
        kind = job.kind
        payload = json.loads(job.payload_json)

    try:
        with SessionLocal() as db:
            if kind == "process_webhook":
                process_webhook_event(db, payload["webhook_event_id"], settings)
            job = db.get(JobModel, job_id)
            if job:
                job.status = "completed"
                job.lease_until = None
                db.commit()
        return True
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(JobModel, job_id)
            if job:
                job.last_error = type(exc).__name__
                job.lease_until = None
                job.status = "pending" if job.attempts < 3 else "failed"
                if job.status == "failed" and kind == "process_webhook":
                    webhook_event = db.get(WebhookEventModel, payload.get("webhook_event_id"))
                    if webhook_event:
                        mark_webhook_enrichment_failed(db, webhook_event.id)
                        webhook_event.payload_json = json.dumps({"event": webhook_event.event_type, "redacted": True})
                audit(
                    db,
                    "failure",
                    "Background job will retry" if job.status == "pending" else "Background job stopped",
                    "Processing failed safely; the raw exception and secrets were not logged.",
                    severity="warning" if job.status == "pending" else "error",
                    metadata={"job_id": job.id, "attempt": job.attempts},
                )
                db.commit()
        return True


async def worker_loop(settings: Settings, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        processed = await asyncio.to_thread(claim_and_process_one, settings)
        if not processed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
