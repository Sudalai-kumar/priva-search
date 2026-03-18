"""
Scorecard ORM models — maps to the `scorecards`, `risk_categories`,
`opt_out_info`, and `scan_jobs` tables in PostgreSQL.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Scorecard(Base):
    """Stores the AI-generated privacy scorecard for a brand."""

    __tablename__ = "scorecards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    overall_risk_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    overall_confidence: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_markdown_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    crawl_method_used: Mapped[str | None] = mapped_column(String(30), nullable=True)
    legal_review_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="scorecards")
    risk_categories: Mapped[list["RiskCategory"]] = relationship(
        "RiskCategory", back_populates="scorecard", cascade="all, delete-orphan"
    )
    opt_out_info: Mapped["OptOutInfo | None"] = relationship(
        "OptOutInfo", back_populates="scorecard", uselist=False, cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_scorecards_brand_id", "brand_id"),
    )


class RiskCategory(Base):
    """Stores the per-category risk score and supporting evidence."""

    __tablename__ = "risk_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id"), nullable=False)
    category_key: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    confidence: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    plain_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_examples: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    scorecard: Mapped["Scorecard"] = relationship("Scorecard", back_populates="risk_categories")

    # Indexes
    __table_args__ = (
        Index("ix_risk_categories_scorecard_id", "scorecard_id"),
        UniqueConstraint("scorecard_id", "category_key", name="uq_risk_categories_scorecard_id_category_key"),
    )


class OptOutInfo(Base):
    """Stores opt-out and data deletion links for a brand scorecard."""

    __tablename__ = "opt_out_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scorecard_id: Mapped[int] = mapped_column(ForeignKey("scorecards.id"), nullable=False)
    gpc_supported: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    do_not_sell_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    deletion_request_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opt_out_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    scorecard: Mapped["Scorecard"] = relationship("Scorecard", back_populates="opt_out_info")

    # Indexes
    __table_args__ = (
        UniqueConstraint("scorecard_id", name="uq_opt_out_info_scorecard_id"),
    )


class ScanJob(Base):
    """Tracks the lifecycle of an async scan pipeline job."""

    __tablename__ = "scan_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    submitted_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_scan_jobs_status", "status"),
        Index("ix_scan_jobs_created_at", "created_at"),
    )
