"""
Centralized model imports for SQLAlchemy and Alembic.
"""

from db.database import Base
from models.brand import Brand
from models.scorecard import OptOutInfo, RiskCategory, ScanJob, Scorecard

__all__ = ["Base", "Brand", "Scorecard", "RiskCategory", "OptOutInfo", "ScanJob"]
