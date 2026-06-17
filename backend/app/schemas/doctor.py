"""名医录 Schema"""
from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel, Field


class DoctorCreate(BaseModel):
    """管理端新增/编辑医生"""
    name: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=100)
    hospital: str = Field(min_length=1, max_length=200)
    title: Optional[str] = Field(default=None, max_length=100)
    diseases: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=50)
    avatar: Optional[str] = Field(default=None, max_length=500)
    bio: Optional[str] = None
    extra: Optional[Any] = None


class DoctorOut(DoctorCreate):
    """返回给前端"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DoctorListResponse(BaseModel):
    """列表分页"""
    items: List[DoctorOut]
    total: int
    page: int
    size: int


class DoctorSearchResult(BaseModel):
    """语义检索单条结果"""
    id: int
    name: str
    department: str
    hospital: str
    title: Optional[str] = None
    diseases: Optional[str] = None
    city: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    score: float
    snippet: str  # 命中的文本片段


class DoctorSearchResponse(BaseModel):
    query: str
    results: List[DoctorSearchResult]
    total: int
