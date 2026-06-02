"""应用生命周期:启动初始化 DB / RAG / LLM"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db
from app.services.rag_service import get_rag_service
from app.utils.logger import logger


async def warmup_rag():
    """启动时预热:从 DB 加载知识构建索引"""
    try:
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.knowledge import Knowledge

        async with AsyncSessionLocal() as db:
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
        rag.initialize()
        if documents and (rag.index is None or rag.index.ntotal == 0):
            rag.build_index(documents)
            logger.info(f"✅ 启动时构建 RAG 索引:{len(documents)} 条")
        else:
            logger.info(f"✅ RAG 索引已就绪:{rag.index.ntotal if rag.index else 0} 条")
    except Exception as e:
        logger.exception(f"RAG 预热失败: {e}")
