"""Agent 服务 Schema"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class SymptomAnalysisRequest(BaseModel):
    symptoms: str = Field(min_length=1, description="症状描述")
    user_context: Optional[dict] = None
    consultation_id: Optional[int] = None  # 提供则把分析结果同步到该问诊


class SymptomAnalysisResponse(BaseModel):
    reply: str
    urgency_level: int = 2  # 1-4
    needs_urgent_care: bool = False
    possible_causes: List[str] = []
    suggested_examinations: List[str] = []
    department: Optional[str] = None
    self_care_tips: List[str] = []
    reference_sources: List[dict] = []


class TriageRequest(BaseModel):
    symptoms: str


class TriageResponse(BaseModel):
    department: str
    urgency_level: int
    urgency_label: str
    reason: str
    reference_sources: List[dict] = []
