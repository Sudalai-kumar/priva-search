"""initial

Revision ID: 0001
Revises: 
Create Date: 2026-03-15 23:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Brands ──────────────────────────────────────────────────────────────
    op.create_table(
        'brands',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('privacy_url', sa.Text(), nullable=True),
        sa.Column('tier', sa.SmallInteger(), server_default='2', nullable=False),
        sa.Column('crawl_blocked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_brands_slug', 'brands', ['slug'], unique=True)

    # ─── Scorecards ──────────────────────────────────────────────────────────
    op.create_table(
        'scorecards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('overall_risk_score', sa.SmallInteger(), nullable=True),
        sa.Column('overall_confidence', sa.SmallInteger(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('trust_status', sa.String(length=20), nullable=True),
        sa.Column('last_scanned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_markdown_snapshot', sa.Text(), nullable=True),
        sa.Column('policy_hash', sa.String(length=64), nullable=True),
        sa.Column('model_used', sa.String(length=50), nullable=True),
        sa.Column('crawl_method_used', sa.String(length=30), nullable=True),
        sa.Column('legal_review_recommended', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scorecards_brand_id', 'scorecards', ['brand_id'], unique=False)

    # ─── Risk Categories ─────────────────────────────────────────────────────
    op.create_table(
        'risk_categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scorecard_id', sa.Integer(), nullable=False),
        sa.Column('category_key', sa.String(length=50), nullable=False),
        sa.Column('score', sa.SmallInteger(), nullable=True),
        sa.Column('confidence', sa.SmallInteger(), nullable=True),
        sa.Column('found', sa.Boolean(), nullable=True),
        sa.Column('plain_summary', sa.Text(), nullable=True),
        sa.Column('score_reason', sa.Text(), nullable=True),
        sa.Column('risk_examples', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['scorecard_id'], ['scorecards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_categories_scorecard_id', 'risk_categories', ['scorecard_id'], unique=False)

    # ─── Opt Out Info ────────────────────────────────────────────────────────
    op.create_table(
        'opt_out_info',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scorecard_id', sa.Integer(), nullable=False),
        sa.Column('gpc_supported', sa.Boolean(), nullable=True),
        sa.Column('do_not_sell_url', sa.Text(), nullable=True),
        sa.Column('deletion_request_url', sa.Text(), nullable=True),
        sa.Column('privacy_contact_email', sa.String(length=255), nullable=True),
        sa.Column('opt_out_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['scorecard_id'], ['scorecards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # ─── Scan Jobs ───────────────────────────────────────────────────────────
    op.create_table(
        'scan_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('brand_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scan_jobs_created_at', 'scan_jobs', ['created_at'], unique=False)
    op.create_index('ix_scan_jobs_status', 'scan_jobs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('scan_jobs')
    op.drop_table('opt_out_info')
    op.drop_table('risk_categories')
    op.drop_table('scorecards')
    op.drop_table('brands')
