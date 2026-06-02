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
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        # 批量调用
        all_vecs = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = await client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            all_vecs.extend([d.embedding for d in resp.data])
        return np.array(all_vecs, dtype="float32")


# 全局单例
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
