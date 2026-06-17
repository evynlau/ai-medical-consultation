"""RAG 服务 - 检索增强生成核心"""
import asyncio
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, List, Dict, Optional

import numpy as np

from app.core.config import settings
from app.services.embedding import get_embedding_service
from app.utils.logger import logger


class RAGService:
    """RAG 检索服务
    - 离线: 把知识库文本向量化,写入 FAISS 索引
    - 在线: 用户问题 → 向量检索 → 关键词加权 → 返回 Top-K

    异步重建:
    - request_reindex() 立即返回,任务丢进 asyncio.Queue 在后台 worker 协程中跑
    - 多余请求会被合并(队列容量=1,新的会替换旧的)
    - 状态通过 get_reindex_status() 实时查询
    """

    INDEX_DIR = Path("./data/faiss_index")
    INDEX_FILE = INDEX_DIR / "index.faiss"
    META_FILE = INDEX_DIR / "metadata.json"

    # reindex 状态机: idle / queued / running / finished / error
    STATUS_IDLE = "idle"
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_FINISHED = "finished"
    STATUS_ERROR = "error"

    def __init__(self):
        self.embedding = get_embedding_service()
        self.index = None
        self.documents: List[Dict] = []  # 原始文档 [{id, title, content, category, ...}]
        self._loaded = False
        # 索引持久化时存的"签名"(SHA-256 文档签名),用于启动期跳过重建
        self._saved_signature: Optional[str] = None

        # ===== 异步 reindex 状态 =====
        self._reindex_lock = threading.Lock()
        self._reindex_status: str = self.STATUS_IDLE
        self._reindex_progress: dict = {}   # {current, total, started_at, finished_at, error}
        self._reindex_queue: Optional[asyncio.Queue] = None
        self._reindex_worker_task: Optional[asyncio.Task] = None
        self._reindex_loop: Optional[asyncio.AbstractEventLoop] = None

    def initialize(self):
        """加载已有索引(若存在)"""
        if self._loaded:
            return
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)

        if self.INDEX_FILE.exists() and self.META_FILE.exists():
            try:
                import faiss
                self.index = faiss.read_index(str(self.INDEX_FILE))
                raw = json.loads(self.META_FILE.read_text(encoding="utf-8"))
                # 兼容旧版 metadata.json 是 list 的情况
                if isinstance(raw, list):
                    self.documents = raw
                    self._saved_signature = None
                else:
                    # 新版:{documents: [...], _signature: "..."}
                    self.documents = raw.get("documents", [])
                    self._saved_signature = raw.get("_signature")
                logger.info(
                    f"✅ 加载 RAG 索引: {self.index.ntotal} 条"
                    f"{f',签名 {self._saved_signature[:8]}...' if self._saved_signature else ' (旧版无签名)'}"
                )
            except Exception as e:
                logger.warning(f"加载索引失败,将重建: {e}")
                self.index = None
                self.documents = []
                self._saved_signature = None
        self._loaded = True

    def reload_from_disk(self) -> None:
        """重读磁盘上的索引文件(用于 reindex 完成后让内存立即生效)

        使用场景:管理后台触发 _rebuild_index 后,本进程内存里的 index/documents
        仍是旧的。调用本方法清缓存并重新 initialize,无需重启服务。
        """
        logger.info("[RAG] reload_from_disk:重新读取索引")
        self.index = None
        self.documents = []
        self._loaded = False
        self.initialize()

    def build_index(self, documents: List[Dict], embed_timeout: Optional[float] = None) -> int:
        """从零构建索引
        documents: [{id, title, content, category, tags, source}, ...]
        embed_timeout: 单次向量化允许的最大耗时(秒)。
                      None 时使用 settings.EMBED_TIMEOUT(默认 24h,基本无限)
        返回索引条数
        """
        if embed_timeout is None:
            embed_timeout = settings.EMBED_TIMEOUT
        if not documents:
            return 0

        # 准备检索文本:title + tags + content
        texts = []
        for d in documents:
            tags = d.get("tags") or ""
            text = f"{d.get('title', '')}。{tags}。{d.get('content', '')}".strip()
            texts.append(text)

        # 向量化 — 用独立线程跑 async(避免 uvicorn uvloop 冲突)
        logger.info(f"开始向量化 {len(texts)} 条知识(超时={embed_timeout}s)...")
        embeddings = self._run_async(self.embedding.embed(texts), timeout=embed_timeout)
        if embeddings is None:
            raise RuntimeError(
                f"embedding 嵌入超时(>{embed_timeout}s),换更小模型或调高 embed_timeout"
            )
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

    def _run_async(self, coro, timeout: float = 180.0):
        """在独立线程中跑 async 协程(避开 uvicorn 的 uvloop)
        与 OCR 服务同款方案,详见 app/services/ocr_service.py
        timeout 默认 180s;大 embedding 模型(qwen3-embedding:4b 681 条 ~150s)
        调用方传 600s 留余量。
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
        t.join(timeout=timeout)

        if t.is_alive():
            logger.error(f"[RAG] _run_async 超时({timeout}s),嵌入仍在跑但本调用放弃")
            return None
        if result_holder["error"]:
            raise result_holder["error"]
        return result_holder["value"]

    def _save(self):
        """持久化索引"""
        import faiss
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.INDEX_FILE))
        # 把签名指纹也存到 metadata.json(下次启动对比)
        signature = self.compute_signature(self.documents)
        payload = {
            "documents": self.documents,
            "_signature": signature,
        }
        self.META_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    @staticmethod
    def compute_signature(documents: List[Dict]) -> str:
        """计算文档集合的"签名"指纹。
        - DB 文档:用 updated_at(模型已有 onupdate 触发)
        - 文件文档:用 (mtime, size) —— 文件源 mtime 稳定,本地编辑一定变
        返回 64 字符 SHA-256
        """
        sig_input = []
        for d in documents:
            doc_id = d.get("id", "")
            # 文件源 id 形如 "file_xxx.md",DB 源形如 "kb_123" / "dr_45"
            entry = {"id": doc_id}
            # 优先用 mtime+size(文件源)
            if "mtime" in d and "size" in d:
                entry["mtime"] = d["mtime"]
                entry["size"] = d["size"]
            else:
                # 否则用 updated_at(DB 源)
                entry["updated_at"] = d.get("updated_at") or ""
            sig_input.append(entry)
        # 排序后序列化,保证顺序无关
        sig_input.sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        raw = json.dumps(sig_input, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def search(self, query: str, top_k: int = 5, score_threshold: Optional[float] = None) -> List[Dict]:
        """同步向量检索(保留向后兼容;新代码请用 asearch)

        实现:在子线程里 asyncio.run(asearch) —— client 跟 loop 一起创建/关闭,
        不会出现 httpx "Event loop is closed"。
        """
        if self.index is None or self.index.ntotal == 0:
            self.initialize()
            if self.index is None or self.index.ntotal == 0:
                return []

        # 同步上下文用 _run_async(子线程起新 loop,client 跟 loop 同生命周期)
        q_vec = self._run_async(self.embedding.embed([query]))
        if q_vec is None:
            return []
        return self._search_with_vec(q_vec, top_k, score_threshold)

    async def asearch(self, query: str, top_k: int = 5, score_threshold: Optional[float] = None) -> List[Dict]:
        """异步向量检索(推荐使用)

        直接 await embedding.embed,跟 FastAPI 的事件循环共用,
        不会触发 httpx "Event loop is closed"。
        """
        if self.index is None or self.index.ntotal == 0:
            self.initialize()
            if self.index is None or self.index.ntotal == 0:
                return []

        q_vec = await self.embedding.embed([query])
        return self._search_with_vec(q_vec, top_k, score_threshold)

    def _search_with_vec(
        self, q_vec, top_k: int, score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """在拿到查询向量后,做归一化 + FAISS 检索 + 后处理"""
        q_vec = np.array(q_vec).astype("float32")
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
        """混合检索 = 向量检索 + 关键词加权(同步版,新代码用 ahybrid_search)"""
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

    async def ahybrid_search(
        self, query: str, keywords: Optional[List[str]] = None, top_k: int = 5
    ) -> List[Dict]:
        """混合检索 async 版(推荐使用)"""
        vector_results = await self.asearch(query, top_k=top_k * 2)
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

    # ============================================================
    # 异步 reindex:丢到后台 worker 协程,不阻塞调用方
    # ============================================================

    def request_reindex(self, documents_loader: Callable[[], List[Dict]]) -> dict:
        """请求一次异步 reindex。
        documents_loader: 同步回调,worker 协程会调用它获取最新文档列表
        立即返回 {"status": "queued"} | {"status": "running", "progress": ...}
        """
        with self._reindex_lock:
            # 启动 worker(只在第一次调用时启动)
            if self._reindex_queue is None:
                self._reindex_loop = asyncio.new_event_loop()
                self._reindex_queue = asyncio.Queue(maxsize=1)
                self._reindex_worker_task = self._reindex_loop.create_task(
                    self._reindex_worker()
                )
                # 在专用线程里跑这个 loop
                t = threading.Thread(
                    target=self._reindex_loop.run_forever, daemon=True, name="rag-reindex"
                )
                t.start()

            # 把任务丢进队列;若队列已满(说明有 pending 任务),先清空再放新的
            if self._reindex_queue.full():
                try:
                    self._reindex_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            self._reindex_status = self.STATUS_QUEUED
            self._reindex_progress = {
                "current": 0, "total": 0,
                "started_at": None, "finished_at": None, "error": None,
            }
            # put_nowait 在 queue 满时会抛 QueueFull,上面已经清空,这里应该不会触发
            self._reindex_loop.call_soon_threadsafe(
                self._reindex_queue.put_nowait, documents_loader
            )
            return {"status": self._reindex_status}

    def get_reindex_status(self) -> dict:
        """查询 reindex 状态(用于前端轮询)"""
        with self._reindex_lock:
            return {
                "status": self._reindex_status,
                "progress": dict(self._reindex_progress),
            }

    async def _reindex_worker(self):
        """后台 worker 协程:从队列取 loader → 跑 build_index → 更新状态"""
        while True:
            loader: Callable[[], List[Dict]] = await self._reindex_queue.get()
            with self._reindex_lock:
                self._reindex_status = self.STATUS_RUNNING
                self._reindex_progress = {
                    "current": 0, "total": 0,
                    "started_at": time.time(), "finished_at": None, "error": None,
                }
            try:
                logger.info("[RAG-reindex] worker 启动,加载文档...")
                documents = await asyncio.get_event_loop().run_in_executor(
                    None, loader
                )
                with self._reindex_lock:
                    self._reindex_progress["total"] = len(documents)
                logger.info(f"[RAG-reindex] 共 {len(documents)} 条,开始向量化...")

                # build_index 内部已经会用线程跑 async embedding,这里直接调
                # 但为了进度更新可控,这里手动拆开走
                if not documents:
                    count = 0
                else:
                    count = await self._build_index_async(documents)

                with self._reindex_lock:
                    self._reindex_status = self.STATUS_FINISHED
                    self._reindex_progress["current"] = count
                    self._reindex_progress["finished_at"] = time.time()
                logger.info(f"[RAG-reindex] 完成: {count} 条")
            except Exception as e:
                logger.exception(f"[RAG-reindex] 失败: {e}")
                with self._reindex_lock:
                    self._reindex_status = self.STATUS_ERROR
                    self._reindex_progress["error"] = str(e)
                    self._reindex_progress["finished_at"] = time.time()
            # 标记 task done,让 queue.get() 下一轮能拿到
            self._reindex_queue.task_done()

    async def _build_index_async(self, documents: List[Dict]) -> int:
        """异步版本 build_index。embed 内部是 async,直接 await 即可
        (IO 等待期间会让出 event loop,不会卡住其他请求)
        """
        # 准备文本
        texts = []
        for d in documents:
            tags = d.get("tags") or ""
            text = f"{d.get('title', '')}。{tags}。{d.get('content', '')}".strip()
            texts.append(text)

        # 直接 await 异步 embed(内部按 100 条/批 + 网络 IO,自然让出 loop)
        embeddings = await self.embedding.embed(texts)
        if embeddings is None:
            raise RuntimeError("embedding 返回 None")
        if len(embeddings) == 0:
            return 0

        # numpy + FAISS
        embeddings = np.array(embeddings).astype("float32")
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embeddings = embeddings / norms

        import faiss
        dim = embeddings.shape[1]
        new_index = faiss.IndexFlatIP(dim)
        new_index.add(embeddings)

        # 写盘 + 切换内存引用
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(new_index, str(self.INDEX_FILE))
        # 同步写入签名,下次启动才能判断是否跳过
        signature = self.compute_signature(documents)
        self.META_FILE.write_text(
            json.dumps(
                {"documents": documents, "_signature": signature},
                ensure_ascii=False, default=str,
            ),
            encoding="utf-8",
        )
        self.index = new_index
        self.documents = documents
        self._loaded = True
        self._saved_signature = signature
        return len(documents)


# 单例
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
        _rag_service.initialize()
    return _rag_service
