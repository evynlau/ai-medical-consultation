"""/api/v1/knowledge - 知识库 CRUD + 检索"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import get_db
from app.models.knowledge import Knowledge
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeOut,
    KnowledgeSearchResult, KnowledgeSearchResponse,
)
from app.services.rag_service import get_rag_service

router = APIRouter()


@router.get("", response_model=list[KnowledgeOut])
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = select(Knowledge)
    if category:
        stmt = stmt.where(Knowledge.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(Knowledge.title.like(like), Knowledge.content.like(like), Knowledge.tags.like(like))
        )
    stmt = stmt.order_by(Knowledge.id.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get("/{kb_id}", response_model=KnowledgeOut)
async def get_knowledge(kb_id: int, db: AsyncSession = Depends(get_db)):
    kb = await db.get(Knowledge, kb_id)
    if not kb:
        raise HTTPException(404, "知识不存在")
    return kb


@router.post("", response_model=KnowledgeOut, status_code=201)
async def create_knowledge(payload: KnowledgeCreate, db: AsyncSession = Depends(get_db)):
    kb = Knowledge(**payload.model_dump())
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    # 重建索引
    await _rebuild_index(db)
    return kb


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge(kb_id: int, db: AsyncSession = Depends(get_db)):
    kb = await db.get(Knowledge, kb_id)
    if not kb:
        raise HTTPException(404, "知识不存在")
    await db.delete(kb)
    await db.commit()
    await _rebuild_index(db)
    return None


@router.post("/reindex", status_code=200)
async def reindex(db: AsyncSession = Depends(get_db)):
    """手动重建向量索引"""
    count = await _rebuild_index(db)
    return {"message": "reindexed", "count": count}


@router.get("/search/query", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
):
    """向量检索(不需登录,公开)"""
    rag = get_rag_service()
    results = rag.hybrid_search(query=q, top_k=top_k)
    snippets = []
    for r in results:
        content = r.get("content", "")
        snippet = content[:200] + ("..." if len(content) > 200 else "")
        snippets.append(KnowledgeSearchResult(
            id=r.get("id", 0),
            title=r.get("title", ""),
            category=r.get("category", ""),
            content=content,
            tags=r.get("tags"),
            score=round(r.get("score", 0), 4),
            snippet=snippet,
        ))
    return KnowledgeSearchResponse(query=q, results=snippets, total=len(snippets))


# ====================== 内部 ======================

async def _rebuild_index(db: AsyncSession) -> int:
    """从数据库读取全部知识,重建向量索引"""
    rows = (await db.execute(select(Knowledge))).scalars().all()
    documents = [
        {
            "id": kb.id,
            "title": kb.title,
            "content": kb.content,
            "category": kb.category,
            "tags": kb.tags or "",
            "source": kb.source or "",
        }
        for kb in rows
    ]
    rag = get_rag_service()
    return rag.build_index(documents)
