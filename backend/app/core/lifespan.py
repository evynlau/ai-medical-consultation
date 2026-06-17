"""应用生命周期:启动初始化 DB / RAG / LLM"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db
from app.services.rag_service import get_rag_service
from app.utils.logger import logger


async def warmup_rag():
    """启动时加载 RAG 索引(只读盘,从不向量化)

    设计:
    - 启动期只做"加载磁盘索引"(< 100ms),不做任何 embedding 计算
    - 如果磁盘无索引 → index 为空,搜索会返回空,直到管理员手动触发重建
    - 向量化迁移到管理端 /admin/knowledge-index 页面显式触发
    - 理由:启动期向量化(5+ 分钟)会拖慢服务启动、影响使用
    """
    try:
        rag = get_rag_service()
        rag.initialize()
        if rag.index is not None and rag.index.ntotal > 0:
            sig_short = (rag._saved_signature or "<旧版无签名>")[:12]
            logger.info(
                f"✅ RAG 索引已加载:{rag.index.ntotal} 条 "
                f"(签名 {sig_short}...,启动期不做向量化)"
            )
        else:
            logger.warning(
                "⚠️  RAG 索引为空(磁盘无 index.faiss),"
                "搜索将返回空结果 — 请在管理端 /admin/knowledge-index 触发「重建索引」"
            )
    except Exception as e:
        logger.exception(f"RAG 索引加载失败: {e}")
