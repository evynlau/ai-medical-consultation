"""知识库 Schema"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=50)
    content: str
    tags: Optional[str] = None
    source: Optional[str] = None


class KnowledgeOut(BaseModel):
    id: int
    title: str
    category: str
    content: str
    tags: Optional[str]
    source: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeSearchResult(BaseModel):
    id: int
    title: str
    category: str
    content: str
    tags: Optional[str]
    score: float
    snippet: str  # 检索内容片段


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[KnowledgeSearchResult]
    total: int
