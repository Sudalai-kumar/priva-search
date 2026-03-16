"""
Database configuration — async SQLAlchemy 2.0 engine and session factory.

Uses asyncpg driver. DATABASE_URL must use the postgresql+asyncpg:// scheme.
"""

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine, text

from alembic.config import Config
from alembic import command

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://privasearch:privasearch_secret@localhost:5432/privasearch",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # Set True to log all SQL (dev only)
    pool_pre_ping=True,  # Detect stale connections
    pool_size=10,
    max_overflow=20,
)

# ─────────────────────────────────────────────────────────────────────────────
# Session factory
# ─────────────────────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Declarative base — all ORM models inherit from this
# ─────────────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependency
# ─────────────────────────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    Yields an async database session for use as a FastAPI dependency.
    Automatically closes the session when the request completes.
    """
    async with AsyncSessionLocal() as session:
        yield session


def run_migrations():
    """Run Alembic migrations 'upgrade head' using the synchronous Python API."""
    try:
        logger.info("Running database migrations...")
        
        # Alembic command.upgrade requires a sync connection string
        # We replace asyncpg with psycopg2 or similar if needed, 
        # but Alembic works fine with the base postgresql:// dialect via SQLAlchemy sync.
        sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        
        # Run upgrade head
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✅ Migrations applied (head).")
    except Exception as exc:
        logger.error("❌ Migration failed: %s", exc)
        # We don't raise here to allow the app to try starting anyway, 
        # but in production this should probably be a hard fail.


# ─────────────────────────────────────────────────────────────────────────────
# Connectivity test (used by /health endpoint and startup hook)
# ─────────────────────────────────────────────────────────────────────────────
async def test_db_connection() -> bool:
    """Execute a simple SELECT 1 to verify the database is reachable."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connection test failed: %s", exc)
        return False
