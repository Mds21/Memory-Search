"""In-process worker pool. Same contract as a Celery task (idempotent, retried, status recorded in `jobs`),
so it can be replaced by Celery+Redis without touching the pipelines."""
import logging
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..adapters import registry
from ..config import get_settings
from ..db import SessionLocal
from ..models import Asset, Job
from .document import ingest_document
from .photo import ingest_photo
from .video import ingest_video

log = logging.getLogger("smriti.worker")
_pool: ThreadPoolExecutor | None = None
_STAGE = {"photo": ingest_photo, "video": ingest_video, "document": ingest_document}


def pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=get_settings().worker_concurrency, thread_name_prefix="ingest")
    return _pool


def enqueue(asset_id: str) -> None:
    pool().submit(run_ingest, asset_id)


def run_ingest(asset_id: str, attempts: int = 3) -> None:
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if not asset:
            return
        job = Job(asset_id=asset.id, stage=asset.kind, status="running")
        db.add(job)
        asset.status, asset.status_detail = "processing", "starting"
        db.commit()
        src = registry.store().path(f"{asset.owner_id}/{asset.id}/original{Path(asset.filename).suffix.lower()}")
        err = None
        for n in range(1, attempts + 1):
            job.attempts = n
            try:
                _STAGE[asset.kind](db, asset, src)
                asset.status, asset.status_detail, job.status, job.error = "ready", None, "done", None
                db.commit()
                return
            except ValueError as e:  # permanent, human-readable
                db.rollback()
                err = str(e)
                break
            except Exception as e:  # transient: retry with backoff
                db.rollback()
                err = f"{type(e).__name__}: {e}"
                log.warning("ingest %s attempt %s failed: %s", asset_id, n, err)
                time.sleep(min(2 ** n, 8))
        asset = db.get(Asset, asset_id)
        asset.status, asset.status_detail = "failed", (err or "Unknown error")[:500]
        job.status, job.error = "failed", err
        db.commit()
    finally:
        db.close()


def resume_pending() -> int:
    """On startup, re-enqueue assets left queued/processing by a previous run."""
    db = SessionLocal()
    try:
        ids = [a.id for a in db.query(Asset).filter(Asset.status.in_(["queued", "processing"])).all()]
    finally:
        db.close()
    for i in ids:
        enqueue(i)
    return len(ids)
