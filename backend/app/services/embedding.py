"""Embedding 服务 - 三种 provider 统一封装"""
from typing import List
import hashlib
import numpy as np

from app.core.config import settings
from app.utils.logger import logger


class EmbeddingService:
    """文本向量化服务
    - mock: 基于字符哈希,生成稳定伪向量(无需联网,推荐本地演示)
    - local: sentence-transformers 本地模型
    - openai: OpenAI 兼容 embedding 接口
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self.dim = settings.EMBEDDING_DIM
        self._model = None  # 延迟加载

    async def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")

        if self.provider == "mock":
            return self._embed_mock(texts)
        elif self.provider == "local":
            return self._embed_local(texts)
        elif self.provider == "openai":
            return await self._embed_openai(texts)
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

    def _embed_mock(self, texts: List[str]) -> np.ndarray:
        """基于词袋 + 字符 n-gram hash 的简易向量化
        - 优点:零依赖、零下载、确定性
        - 缺点:语义能力弱,只用于演示
        """
        vecs = []
        for text in texts:
            v = np.zeros(self.dim, dtype="float32")
            # 字符级特征
            for token in self._tokenize(text):
                h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
                idx = h % self.dim
                sign = 1.0 if (h & 1) else -1.0
                v[idx] += sign
            # 归一化
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            vecs.append(v)
        return np.stack(vecs)

    def _tokenize(self, text: str) -> List[str]:
        """中英混合分词:对中文按字符切 + 简单英文词切"""
        text = text.lower().strip()
        tokens = []
        # 收集连续英文字母/数字
        i = 0
        buf = []
        for ch in text:
            if "一" <= ch <= "鿿":  # 中文字符
                if buf:
                    tokens.append("".join(buf))
                    buf = []
                tokens.append(ch)
            elif ch.isalnum():
                buf.append(ch)
            else:
                if buf:
                    tokens.append("".join(buf))
                    buf = []
        if buf:
            tokens.append("".join(buf))
        return tokens

    def _embed_local(self, texts: List[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"加载本地 Embedding 模型: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        vecs = self._model.encode(texts, show_progress_bar=False)
        return np.array(vecs).astype("float32")

    async def _embed_openai(self, texts: List[str]) -> np.ndarray:
        from openai import AsyncOpenAI
        # 优先用 embedding 专用配置;留空时回退到 LLM 的 OPENAI_BASE_URL
        base_url = (settings.EMBEDDING_BASE_URL or "").strip() or settings.OPENAI_BASE_URL
        api_key = (settings.EMBEDDING_API_KEY or "").strip() or settings.OPENAI_API_KEY or "ollama"

        # 模型名走 settings.EMBEDDING_MODEL
        model_name = settings.EMBEDDING_MODEL
        if not model_name or model_name == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2":
            # 默认配置(本地 sentence-transformers)对 OpenAI provider 无效,显式兜底
            is_local = "11434" in base_url
            model_name = "nomic-embed-text" if is_local else "text-embedding-3-small"

        # 关键:client 在本函数内创建,跑完用 try/finally 主动 close
        # 否则子线程 loop 关闭时,httpx async generator 会报 "Event loop is closed"
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            # 批量调用
            all_vecs = []
            batch_size = 100
            n_batches = (len(texts) + batch_size - 1) // batch_size
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_no = i // batch_size + 1
                logger.info(
                    f"[Embedding] 批次 {batch_no}/{n_batches} "
                    f"({len(batch)} 条,累计 {i + len(batch)}/{len(texts)})"
                )
                resp = await client.embeddings.create(
                    model=model_name,
                    input=batch,
                )
                all_vecs.extend([d.embedding for d in resp.data])
            return np.array(all_vecs, dtype="float32")
        finally:
            # 在当前 loop 关闭之前显式 aclose client
            # 避免 "Event loop is closed" 错误(子线程 asyncio.run 场景)
            try:
                await client.close()
            except Exception:
                pass


# 全局单例
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
