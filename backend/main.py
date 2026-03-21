"""
Priva-Search — FastAPI Application Entry Point

This module bootstraps the FastAPI application, configures middleware,
registers all routers, runs database migrations, and verifies 
connectivity to PostgreSQL and Redis on startup.
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import engine, get_db, test_db_connection
from routers import brand, optout, scan, search
from services.rate_limiter import setup_rate_limiter
from services.scheduler import start_scheduler, stop_scheduler

# ─────────────────────────────────────────────────────────────────────────────
# Load environment
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("privasearch")

# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — startup / shutdown hooks
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan hook for startup and shutdown events.
    - Validates required environment variables
    - Runs database migrations
    - Verifies connectivity to DB and Redis
    - Starts the APScheduler background re-crawl job
    """
    # 1. Validate environment
    required_keys = ["GROQ_API_KEY", "FIRECRAWL_API_KEY"]
    for key in required_keys:
        if not os.getenv(key):
            logger.warning("Missing %s in environment. AI features may fail.", key)

    # 2. Database migrations are now handled via Docker entrypoint or manual commands
    # to avoid startup hangs in the main application loop.

    # 3. Connectivity check (DB)
    db_ok = await test_db_connection()
    if not db_ok:
        logger.error("❌ Could not connect to Database at startup.")
    else:
        logger.info("✅ Database connection verified.")

    # 4. Connectivity check (Redis)
    redis_ok = await test_redis_connection()
    if not redis_ok:
        logger.error("❌ Could not connect to Redis at startup.")
    else:
        logger.info("✅ Redis connection verified.")

    # 5. Start background scheduler (30-day re-crawl)
    try:
        await start_scheduler()
    except Exception as exc:
        logger.error("❌ Failed to start scheduler: %s", exc)

    yield

    # Shutdown
    await stop_scheduler()
    await engine.dispose()
    logger.info("🛑 Application shutdown complete.")


# ─────────────────────────────────────────────────────────────────────────────
# Redis connectivity test
# ─────────────────────────────────────────────────────────────────────────────
async def test_redis_connection() -> bool:
    """Ping Redis and return True if reachable."""
    import redis.asyncio as aioredis

    try:
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        await r.ping()
        await r.aclose()
        return True
    except Exception as exc:
        logger.error("Redis ping failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Priva-Search API",
    description="Privacy scorecard API — AI analysis of brand privacy policies.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting middleware (slowapi + Redis)
setup_rate_limiter(app)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(search.router)
app.include_router(scan.router)
app.include_router(brand.router)
app.include_router(optout.router)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health_check() -> dict:
    """
    Returns the health status of the API and its dependencies.
    Used by Docker health checks and the frontend status indicator.
    """
    from services.groq_tracker import get_usage_stats

    db_ok = await test_db_connection()
    redis_ok = await test_redis_connection()

    groq_stats = {}
    if redis_ok:
        try:
            groq_stats = await get_usage_stats()
        except Exception:
            pass

    return {
        "status": "ok",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "groq": groq_stats,
    }


@app.get("/debug/db", tags=["debug"])
async def debug_db(db: AsyncSession = Depends(get_db)):
    """
    Debug endpoint to verify database tables are created.
    Returns a list of table names found in the 'public' schema.
    """
    try:
        result = await db.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ))
        rows = result.fetchall()
        tables = [row[0] for row in rows if row[0] != "alembic_version"]
        return {"tables": tables}
    except Exception as exc:
        logger.error("Debug DB failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
