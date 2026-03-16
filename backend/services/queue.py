import os
import uuid
import logging
from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select

from db.database import AsyncSessionLocal
from models.scorecard import ScanJob

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Redis Connection & RQ Setup
# ─────────────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
scan_queue = Queue("scan", connection=redis_conn)

async def enqueue_scan_job(brand_name: str, ip_address: str = None) -> str:
    """
    1. Generates a unique scan_id.
    2. Persists a 'queued' ScanJob row to the database.
    3. Enqueues the worker task to Redis.
    """
    scan_id = str(uuid.uuid4())
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. Create DB record
            new_job = ScanJob(
                id=scan_id,
                brand_name=brand_name,
                status="queued",
                ip_address=ip_address
            )
            db.add(new_job)
            await db.commit()
            
            # 2. Enqueue in Redis
            # We import here to avoid circular dependencies if scan_worker imports queue
            from workers.scan_worker import run_scan_job
            scan_queue.enqueue(run_scan_job, scan_id)
            
            logger.info(f"Enqueued scan job {scan_id} for brand: {brand_name}")
            return scan_id
            
        except Exception as exc:
            logger.error(f"Failed to enqueue scan job: {exc}")
            await db.rollback()
            raise
