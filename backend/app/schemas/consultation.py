"""问诊相关 Schema"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ConsultationCreate(BaseModel):
    chief_complaint: str = Field(min_length=1, max_length=10000)
    user_id: Optional[int] = None  # 允许匿名


class MessageCreate(BaseModel):
    role: str = "user"
    content: str = Field(min_length=1)
    message_type: str = "text"


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    message_type: str
    source_knowledge: Optional[Any] = None
    urgency_level: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConsultationOut(BaseModel):
    id: int
    user_id: Optional[int]
    chief_complaint: str
    status: str
    urgency_level: Optional[int]
    diagnosis_summary: Optional[str]
    recommended_department: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageOut] = []

    class Config:
        from_attributes = True


class ConsultationListItem(BaseModel):
    id: int
    chief_complaint: str
    status: str
    urgency_level: Optional[int]
    recommended_department: Optional[str]
    created_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    consultation_id: int
    content: str


class ChatResponse(BaseModel):
    message: MessageOut
    consultation: ConsultationOut
