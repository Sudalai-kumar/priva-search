"""
Brand ORM model — maps to the `brands` table in PostgreSQL.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Brand(Base):
    """Represents a brand/company whose privacy policy has been (or will be) analyzed."""

    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    privacy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    crawl_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    scorecards: Mapped[list["Scorecard"]] = relationship(
        "Scorecard", back_populates="brand", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_brands_slug", "slug", unique=True),
    )
