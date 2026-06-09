"""RAG 服务 - 检索增强生成核心"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np

from app.core.config import settings
from app.services.embedding import get_embedding_service
from app.utils.logger import logger


class RAGService:
    """RAG 检索服务
    - 离线: 把知识库文本向量化,写入 FAISS 索引
    - 在线: 用户问题 → 向量检索 → 关键词加权 → 返回 Top-K
    """

    INDEX_DIR = Path("./data/faiss_index")
    INDEX_FILE = INDEX_DIR / "index.faiss"
    META_FILE = INDEX_DIR / "metadata.json"

    def __init__(self):
        self.embedding = get_embedding_service()
        self.index = None
        self.documents: List[Dict] = []  # 原始文档 [{id, title, content, category, ...}]
        self._loaded = False

    def initialize(self):
        """加载已有索引(若存在)"""
        if self._loaded:
            return
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)

        if self.INDEX_FILE.exists() and self.META_FILE.exists():
            try:
                import faiss
                self.index = faiss.read_index(str(self.INDEX_FILE))
                self.documents = json.loads(self.META_FILE.read_text(encoding="utf-8"))
                logger.info(f"✅ 加载 RAG 索引: {self.index.ntotal} 条")
            except Exception as e:
                logger.warning(f"加载索引失败,将重建: {e}")
                self.index = None
                self.documents = []
        self._loaded = True

    def build_index(self, documents: List[Dict]) -> int:
        """从零构建索引
        documents: [{id, title, content, category, tags, source}, ...]
        返回索引条数
        """
        if not documents:
            return 0

        # 准备检索文本:title + tags + content
        texts = []
        for d in documents:
            tags = d.get("tags") or ""
            text = f"{d.get('title', '')}。{tags}。{d.get('content', '')}".strip()
            texts.append(text)

        # 向量化 — 用独立线程跑 async(避免 uvicorn uvloop 冲突)
        logger.info(f"开始向量化 {len(texts)} 条知识...")
        embeddings = self._run_async(self.embedding.embed(texts))
        embeddings = np.array(embeddings).astype("float32")

        # 构建 FAISS 索引 (使用归一化向量 + 内积,等价余弦)
        import faiss
        dim = embeddings.shape[1]
        # L2 归一化
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embeddings = embeddings / norms

        self.index = faiss.IndexFlatIP(dim)  # 内积 = 余弦相似度
        self.index.add(embeddings)
        self.documents = documents
        self._save()

        logger.info(f"✅ RAG 索引构建完成: {len(documents)} 条, dim={dim}")
        return len(documents)

    def _run_async(self, coro):
        """在独立线程中跑 async 协程(避开 uvicorn 的 uvloop)
        与 OCR 服务同款方案,详见 app/services/ocr_service.py
        """
        import asyncio
        import threading

        result_holder = {"value": None, "error": None}

        def _call():
            try:
                result_holder["value"] = asyncio.run(coro)
            except Exception as e:
                result_holder["error"] = e

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout=180)

        if result_holder["error"]:
            raise result_holder["error"]
        return result_holder["value"]

    def _save(self):
        """持久化索引"""
        import faiss
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.INDEX_FILE))
        self.META_FILE.write_text(
            json.dumps(self.documents, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def search(self, query: str, top_k: int = 5, score_threshold: Optional[float] = None) -> List[Dict]:
        """向量检索"""
        if self.index is None or self.index.ntotal == 0:
            self.initialize()
            if self.index is None or self.index.ntotal == 0:
                return []

        # 用独立线程跑 async 嵌入,绕开 uvicorn uvloop
        q_vec = self._run_async(self.embedding.embed([query]))
        q_vec = np.array(q_vec).astype("float32")
        # 归一化
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm

        threshold = score_threshold if score_threshold is not None else settings.RAG_SCORE_THRESHOLD
        distances, indices = self.index.search(q_vec, min(top_k * 2, self.index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            if dist < threshold:
                continue
            doc = self.documents[idx]
            results.append({
                "id": doc.get("id"),
                "title": doc.get("title"),
                "category": doc.get("category"),
                "content": doc.get("content"),
                "tags": doc.get("tags"),
                "source": doc.get("source"),
                "score": float(dist),
            })
        return results[:top_k]

    def hybrid_search(
        self, query: str, keywords: Optional[List[str]] = None, top_k: int = 5
    ) -> List[Dict]:
        """混合检索 = 向量检索 + 关键词加权"""
        vector_results = self.search(query, top_k=top_k * 2)
        if not vector_results:
            return []

        if keywords:
            for r in vector_results:
                content = (r.get("content", "") + r.get("title", "")).lower()
                matches = sum(1 for kw in keywords if kw.lower() in content)
                r["keyword_score"] = matches / max(len(keywords), 1)
                r["combined_score"] = r["score"] * 0.7 + r["keyword_score"] * 0.3
            vector_results.sort(key=lambda x: x.get("combined_score", x["score"]), reverse=True)

        return vector_results[:top_k]


# 单例
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
        _rag_service.initialize()
    return _rag_service
