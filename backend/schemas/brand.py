from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ScanRequest(BaseModel):
    brand_name: str = Field(..., min_length=1, max_length=255)

class ScanResponse(BaseModel):
    scan_id: str
    status: str

class ScanStatusResponse(BaseModel):
    scan_id: str
    status: str
    progress: int = 0
    slug: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
class BrandSchema(BaseModel):
    id: int
    name: str
    slug: str
    domain: Optional[str] = None
    privacy_url: Optional[str] = None
    tier: int = 1
    crawl_blocked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
