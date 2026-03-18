"""
Scan router — handles job enqueueing, status polling, and WebSocket progress streaming.

Endpoints:
  POST /scan                    — Enqueue a new scan job
  GET  /scan/{scan_id}/status   — HTTP polling fallback
  WS   /ws/scan/{scan_id}       — Real-time progress via Redis pub/sub
"""

import json
import logging
import os

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.scorecard import ScanJob
from services.queue import enqueue_scan_job
from schemas.brand import ScanRequest, ScanResponse, ScanStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

STAGE_PROGRESS = {
    "queued":     5,
    "discovery":  20,
    "crawling":   45,
    "analyzing":  75,
    "validating": 90,
    "done":       100,
    "failed":     0,
}

# ─────────────────────────────────────────────────────────────────────────────
# POST /scan — Enqueue a new scan job
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScanResponse)
async def create_scan(request: ScanRequest, req: Request):
    """
    Starts a new privacy scan for a brand.
    Returns the scan ID which can be used to poll status or connect via WebSocket.
    """
    client_ip = req.client.host if req.client else None

    try:
        scan_id = await enqueue_scan_job(request.url, client_ip)
        return ScanResponse(scan_id=scan_id, status="queued")
    except Exception as exc:
        logger.error("Failed to queue scan: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to queue scan: {str(exc)}")


# ─────────────────────────────────────────────────────────────────────────────
# GET /scan/{scan_id}/status — HTTP polling fallback
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/scan/{scan_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(scan_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves the current status and progress percentage of a scan job.
    Used as a polling fallback when WebSocket is unavailable.
    """
    from services.brand_discovery import slugify

    result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    progress = STAGE_PROGRESS.get(job.status, 0)
    slug = slugify(job.brand_name) if job.brand_name else None

    return ScanStatusResponse(
        scan_id=job.id,
        status=job.status,
        progress=progress,
        slug=slug,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


# ─────────────────────────────────────────────────────────────────────────────
# WS /ws/scan/{scan_id} — Real-time progress via Redis pub/sub
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/scan/{scan_id}")
async def websocket_scan_progress(websocket: WebSocket, scan_id: str):
    """
    WebSocket endpoint that streams real-time scan progress events.

    The worker publishes JSON payloads to the Redis channel:
        scan:{scan_id}:progress

    This handler subscribes to that channel and forwards every message
    to the connected frontend client. Closes automatically when the
    stage is 'done' or 'failed'.

    Falls back gracefully: if no message arrives within IDLE_TIMEOUT_SECONDS
    the connection is closed and the client should switch to polling.
    """
    await websocket.accept()
    logger.info("WebSocket connected for scan_id=%s", scan_id)

    IDLE_TIMEOUT_SECONDS = 300  # 5 minutes max per scan

    redis: aioredis.Redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    channel = f"scan:{scan_id}:progress"

    try:
        await pubsub.subscribe(channel)
        logger.info("Subscribed to Redis channel: %s", channel)

        # Send an initial 'queued' event so the client sees something immediately
        initial_event = {
            "stage": "queued",
            "message": "Your scan is queued",
            "progress": 5,
        }
        await websocket.send_text(json.dumps(initial_event))

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                payload = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning("Malformed message on channel %s: %s", channel, message["data"])
                continue

            # Forward to client
            await websocket.send_text(json.dumps(payload))

            stage = payload.get("stage", "")
            if stage in ("done", "failed"):
                logger.info(
                    "Scan %s reached terminal stage '%s' — closing WebSocket.",
                    scan_id,
                    stage,
                )
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected for scan_id=%s", scan_id)
    except Exception as exc:
        logger.error("WebSocket error for scan_id=%s: %s", scan_id, exc)
        try:
            await websocket.send_text(
                json.dumps({"stage": "failed", "message": "Internal error", "progress": 0})
            )
        except Exception:
            pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket cleanup complete for scan_id=%s", scan_id)
