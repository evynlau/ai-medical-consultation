"""OCR 相关 Schema"""
from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel, Field


class OcrUploadResponse(BaseModel):
    id: int
    image_type: str
    file_name: str
    file_size: int
    ocr_engine: str
    confidence: float
    raw_text: str
    structured_data: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OcrRecordListItem(BaseModel):
    id: int
    image_type: str
    file_name: str
    file_size: int
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


class OcrRecordDetail(OcrRecordListItem):
    raw_text: str
    structured_data: Optional[Any] = None
    ocr_engine: str
