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
    # RAG 索引里 3 类文档统一编码: kb_6(知识库) / dr_5(医生) / file_阿司匹林.md(知识库 .md)
    # 前端拿到字符串 ID 直接传回 /knowledge/{id},后端 get_knowledge 会兼容 kb_xxx 格式
    id: str
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
