import os
import uuid
import logging
from redis import Redis
from rq import Queue
from sqlalchemy import insert

from db.database import AsyncSessionLocal
from models.scorecard import ScanJob

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Redis Connection & RQ Setup
# ─────────────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
scan_queue = Queue("scan", connection=redis_conn)

async def enqueue_scan_job(url: str, ip_address: str = None) -> str:
    """
    1. Generates a unique scan_id.
    2. Persists a 'creating' ScanJob row to the database.
    3. Enqueues the worker task to Redis.
    4. Transitions to 'queued' or 'failed' based on Redis success.
    """
    scan_id = str(uuid.uuid4())
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. Create DB record in 'creating' state
            new_job = ScanJob(
                id=scan_id,
                submitted_url=url,
                status="creating",
                ip_address=ip_address
            )
            db.add(new_job)
            await db.commit()
            
            # 2. Enqueue in Redis
            from workers.scan_worker import run_scan_job
            try:
                scan_queue.enqueue(run_scan_job, scan_id)
            except Exception as redis_exc:
                logger.error(f"Redis enqueue failed for {scan_id}: {redis_exc}")
                new_job.status = "failed"
                new_job.error_message = "Internal queue error: Redis enqueue failed."
                db.add(new_job)
                await db.commit()
                raise redis_exc
            
            # 3. Success, transition to queued
            new_job.status = "queued"
            db.add(new_job)
            await db.commit()
            
            logger.info(f"Successfully enqueued scan job {scan_id} for url: {url}")
            return scan_id
            
        except Exception as exc:
            logger.error(f"Failed to enqueue scan job: {exc}")
            await db.rollback()
            raise
