# RAG 检索增强生成 — 实现文档

> 本项目 RAG 模块位于 `backend/app/services/` + `scripts/init_kb.py`,约 400 行,实现了"**医学知识向量检索 + 关键词加权 + LLM 上下文组装**"的完整链路。

---

## 📐 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                       RAG 架构全景                                │
└──────────────────────────────────────────────────────────────────┘

   ═══ 离线(知识库构建) ═══                                    ═══ 在线(实时检索) ═══
                                                                  
   knowledge_base/*.md                                            用户提问
   (Markdown 文档)                                                    │
       │                                                              ▼
       ▼                                                        MedicalAgent
   scripts/init_kb.py                                          .analyze_symptoms()
       │                                                              │
       │ 1. 解析 MD                                                    │
       ▼                                                              ▼
   ┌─────────┐      ┌──────────────────┐                  RAGService
   │  SQLite │ ───► │ Embedding Service │                      │
   │ (Knowledge)     │ (向量化)         │                      │
   └─────────┘      └────────┬─────────┘                      │
       │                      │                                 │
       │ 2. 标题/标签/内容     │                                 │
       ▼                      ▼                                 │
   ┌─────────────────────────────────┐                         │
   │ FAISS 索引 (IndexFlatIP)        │                         │
   │  + metadata.json (原始文档)      │                         │
   └────────┬────────────────────────┘                         │
            │                                                    │
            │ 3. 启动时加载                                      │
            ▼                                                    │
       RAGService 单例 ◄──────────────────────────────────────────┘
            │
            │ 4. search(query, top_k=5)
            │    └─ 向量召回 + 关键词加权
            ▼
       Top-K 相关知识
            │
            ▼
       组装到 LLM Prompt:
       【相关医学知识参考】
       1. 《高血压》... 相似度 0.85
       2. 《冠心病》... 相似度 0.72
            │
            ▼
       LLM 生成回复(基于检索结果,降低幻觉)
```

---

## 🧩 三大核心组件

### 1. `backend/app/services/embedding.py` — Embedding 服务

把文本转为向量。**三种 provider 自动切换**:

| Provider | 原理 | 依赖 | 适用 |
|---|---|---|---|
| `mock` | 字符 n-gram 哈希 + 归一化 | 零依赖(默认) | 演示、CI、零资源场景 |
| `local` | sentence-transformers 本地模型 | 首次下载 ~120MB | 本地语义检索 |
| `openai` | OpenAI `text-embedding-3-small` | API Key | 生产质量 |

**核心实现**(`_embed_mock`):
```python
def _embed_mock(self, texts: List[str]) -> np.ndarray:
    vecs = []
    for text in texts:
        v = np.zeros(self.dim, dtype="float32")
        for token in self._tokenize(text):  # 中英混合分词
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % self.dim
            sign = 1.0 if (h & 1) else -1.0
            v[idx] += sign
        # 归一化
        v = v / (np.linalg.norm(v) or 1.0)
        vecs.append(v)
    return np.stack(vecs)
```

**关键设计**:
- 中英混合分词:中文按字符切(无 jieba 依赖),英文按词切
- 哈希到固定维度(默认 384),保证 mock 和 local/openai 可互换
- 输出形状固定 `(N, dim)`,FAISS 接口统一

### 2. `backend/app/services/rag_service.py` — RAG 核心

**离线构建 + 在线检索 双模式**:

| 方法 | 用途 | 何时调用 |
|---|---|---|
| `initialize()` | 启动时加载已有索引 | lifespan 启动 |
| `build_index(docs)` | 从零构建/重建索引 | `init_kb.py`、知识增删后 |
| `search(query, top_k)` | 纯向量检索 | 通用检索 |
| `hybrid_search(query, keywords, top_k)` | 向量 + 关键词加权 | 医疗问诊主用 |

**关键实现**(`hybrid_search`):
```python
# 1) 向量召回 top_k*2
vector_results = self.search(query, top_k=top_k * 2)

# 2) 关键词加权(70% 向量 + 30% 关键词命中)
for r in vector_results:
    content = (r["content"] + r["title"]).lower()
    matches = sum(1 for kw in keywords if kw.lower() in content)
    r["keyword_score"] = matches / max(len(keywords), 1)
    r["combined_score"] = r["score"] * 0.7 + r["keyword_score"] * 0.3

# 3) 按 combined_score 排序,返回 top_k
vector_results.sort(key=lambda x: x["combined_score"], reverse=True)
return vector_results[:top_k]
```

**为什么用 `IndexFlatIP`(内积)而不是 `IndexFlatL2`(欧氏距离)?**
- 向量已 L2 归一化(欧氏归一化后,内积 = 余弦相似度)
- 余弦相似度对向量长度不敏感,更关注方向(语义)
- 比 `IndexFlatIP` 的 L2 距离更符合文本检索直觉

**持久化结构**:
```
backend/data/faiss_index/
├── index.faiss      # FAISS 二进制索引
└── metadata.json    # 原始文档数组(对应索引 id)
```

### 3. `scripts/init_kb.py` — 知识库初始化

把 `knowledge_base/*.md` 灌进数据库 + 构建 FAISS 索引。

**Markdown 解析规则**:
```python
# 第一个 # 标题 → knowledge.title
# ## 二级标题 → ### 在 content 中(降级为三级)
# - 列表项 → content 一行
# 列表项第一个词(1-12 字符)→ 自动作为 tag
```

**入库流程**:
1. 遍历 `knowledge_base/{diseases,drugs,examinations,guidelines}/*.md`
2. 解析每篇 MD
3. SQL 查重(`title + category` 唯一)
4. 批量插入到 `Knowledge` 表
5. 收集所有文档 → `rag_service.build_index()`

**幂等性**:重复执行不会重复插入(查重逻辑)。

---

## 🔄 端到端数据流

### 离线阶段(一次)

```
knowledge_base/普通感冒.md
    ↓ parse_markdown()
{
  "title": "普通感冒",
  "content": "感冒多为病毒感染,5-7 天可自愈...",
  "tags": "病毒,感染,自愈",
  "category": "disease"
}
    ↓ INSERT INTO knowledge
SQLite row(id=1, title=..., content=..., category=...)
    ↓ build_index([{id:1, ...}, ...])
FAISS IndexFlatIP(dim=384) + metadata.json
```

### 在线阶段(每次问诊)

```
用户: "头痛 3 天,伴有低烧"
    ↓ MedicalAgent.analyze_symptoms(symptoms)
    ↓ RAGService.hybrid_search(query="头痛 3 天伴有低烧", top_k=5)
        ↓
        1. EmbeddingService.embed(["头痛 3 天伴有低烧"])
            → np.array shape (1, 384)  # 查询向量
        2. FAISS index.search(q_vec, k=10)
            → distances, indices  # top-10 余弦相似度
        3. 过滤 score < RAG_SCORE_THRESHOLD (0.2)
        4. 关键词加权(本场景无关键词,跳过)
        5. 返回 top-5
    ↓
[
  {id:1, title:"偏头痛", content:"...", score:0.85},
  {id:14, title:"急性胸痛识别与处理", content:"...", score:0.45},
  ...
]
    ↓ 拼接到 LLM Prompt
【相关医学知识参考】
1. 《偏头痛》(disease)
   偏头痛是一种常见的慢性神经血管性疾病... [500 字]
2. 《急性胸痛识别与处理》(guideline)
   ...
    ↓ LLM 基于这些知识生成分析
reply: "..."
```

---

## ⚙️ 配置项(`backend/.env`)

```bash
# Embedding 引擎
EMBEDDING_PROVIDER=mock              # mock | local | openai
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384

# RAG 检索参数
RAG_TOP_K=5                         # 召回数量
RAG_SCORE_THRESHOLD=0.2             # 相似度阈值,低于此分数的丢弃
```

**生产推荐配置**:
```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small  # OpenAI 默认
# 或
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5  # 中文语义强
EMBEDDING_DIM=512
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.3
```

---

## 📊 知识库结构

```
knowledge_base/
├── diseases/        → category="disease"     (疾病知识)
├── drugs/           → category="drug"        (药品说明)
├── examinations/    → category="examination" (检查项目)
└── guidelines/      → category="guideline"   (临床指南)
```

每篇 Markdown 规范:
- 第一个 `#` 标题 = `title`
- 列表项首词(1-12 字)= 自动 `tags`
- 其余 = `content`

**当前规模**: 16 篇(7 病 / 4 药 / 2 检查 / 3 指南)

**扩展方式**(3 种):
1. **文件**: 放 `.md` 到对应目录,跑 `init_kb.py`
2. **API**: `POST /api/v1/admin/knowledge`(管理员权限)
3. **管理后台 UI**: 知识库管理 tab → 新增/编辑

---

## 🛠️ 常见操作

### 重建索引(知识变更后)

```bash
# 方式 1:重新 init(也会重建索引)
python scripts/init_kb.py

# 方式 2:仅重建索引(不写 DB,适合调 Embedding 后)
curl -X POST http://localhost:8000/api/v1/admin/knowledge/reindex \
  -H "Authorization: Bearer $TOKEN"

# 方式 3:管理后台 UI
# /admin/knowledge → 点"重建索引"按钮
```

### 切换到真 Embedding

```bash
# .env
EMBEDDING_PROVIDER=local  # 或 openai

# 重新构建索引(用新 embedding 重新向量化所有文档)
python scripts/init_kb.py
```

### 添加新知识(代码方式)

```python
from app.models.knowledge import Knowledge
from app.core.database import AsyncSessionLocal
import asyncio

async def add_kb():
    async with AsyncSessionLocal() as db:
        kb = Knowledge(
            title="心肌梗死急救",
            category="guideline",
            content="...",
            tags="心梗,急救",
        )
        db.add(kb)
        await db.commit()
        # 重建索引
        from app.services.rag_service import get_rag_service
        rag = get_rag_service()
        all_docs = (await db.execute(select(Knowledge))).scalars().all()
        rag.build_index([{... for each kb ...}])

asyncio.run(add_kb())
```

### 调 RAG 检索参数

```python
# 代码层
from app.services.rag_service import get_rag_service
rag = get_rag_service()
results = rag.hybrid_search(
    query="头痛",
    keywords=["偏头痛", "紧张性头痛"],
    top_k=10
)
for r in results:
    print(f"{r['title']}: combined={r.get('combined_score', r['score']):.3f}")
```

---

## 🚀 可扩展点

### 1. 升级到更准的 Embedding

**当前 mock 的限制**:基于字符哈希,语义能力极弱,只能匹配字面相近的词。

**升级路径**:
- **本地**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`(多语言,中文 OK)
- **中文强**: `BAAI/bge-small-zh-v1.5` / `BAAI/bge-large-zh-v1.5`
- **医疗专用**: `DMetaSoul/sbert-chinese-medical-voc-distil` (社区微调)
- **云端**: OpenAI `text-embedding-3-small` / `text-embedding-3-large`

**换装步骤**:
```bash
pip install sentence-transformers  # 已是 requirements
# .env
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DIM=512
# 重建索引
python scripts/init_kb.py
```

### 2. 升级到混合检索 + Rerank

**当前**: 向量召回 + 简单关键词加权
**升级**: 加 BM25 召回 + Reranker 重排

```python
# 升级版 hybrid_search
def hybrid_search(self, query, top_k=5):
    # 1) 向量召回(语义)
    vec_results = self.search(query, top_k=top_k * 3)

    # 2) BM25 召回(关键词)
    bm25_results = self.bm25_search(query, top_k=top_k * 3)

    # 3) RRF 融合
    rrf_score = lambda r, rank: 1 / (60 + rank)
    fused = self.rrf_fuse(vec_results, bm25_results)

    # 4) Reranker 精排(可选)
    # fused = self.rerank(query, fused[:20])[:top_k]

    return fused[:top_k]
```

### 3. 知识分块(Chunking)

**当前**: 一篇 MD = 一个文档
**升级**: 拆成 ~500 字的小块,提高检索粒度

```python
def chunk_text(text: str, chunk_size=500, overlap=50) -> List[str]:
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i+chunk_size])
    return chunks
```

### 4. 多向量(ColBERT 式)

**当前**: 一个文档一个向量
**升级**: 每个 token 一个向量,精细匹配

(实施成本高,通常到 Reranker 阶段就够用)

### 5. 知识图谱增强

把医学概念(疾病 ↔ 症状 ↔ 药品)建成图,检索时既走向量也走图遍历。

(本项目暂未实施,留作未来)

---

## 🔬 性能特征

### 当前实现

| 维度 | 数值 |
|---|---|
| 文档规模 | 16 条(可扩展到数千,FAISS `IndexFlatIP` 万级毫秒级) |
| Embedding 维度 | 384(mock) / 768-1536(local/openai) |
| 单次检索延迟 | mock: <1ms / local: ~50ms / openai: ~200ms |
| 内存占用 | mock: 几乎 0 / 1000 docs: ~1.5MB |
| 并发支持 | ✅ FAISS 线程安全,Embedding 单例共享 |

### 适用边界

- ✅ 适用: < 10 万条医学知识 + 中文为主
- ⚠️ 边界: 10-100 万条,需要换 `IndexIVFFlat` 加速
- ❌ 不适用: > 100 万条,需要分片 + 分布式

### 升级路径

| 规模 | 索引类型 | 检索延迟 | 内存 |
|---|---|---|---|
| < 1 万 | `IndexFlatIP`(当前) | <10ms | 低 |
| 1-100 万 | `IndexIVFFlat`(聚类) | <50ms | 中 |
| 100 万+ | `IndexIVFPQ`(量化) | <100ms | 低(压缩) |

---

## 🧪 调试技巧

### 1. 查看当前索引状态

```python
from app.services.rag_service import get_rag_service
rag = get_rag_service()
print(f"索引文档数: {rag.index.ntotal if rag.index else 0}")
print(f"维度: {rag.index.d if rag.index else 'N/A'}")
```

### 2. 直接看检索结果

```python
results = rag.search("头痛", top_k=5)
for r in results:
    print(f"[{r['score']:.3f}] {r['title']}")
```

### 3. 加日志看每次检索

```python
# rag_service.py:search() 已有 logger.info
# 启动后端后,所有 RAG 调用都会输出:
# [RAG] search '头痛' → 5 results (scores: 0.85, 0.72, ...)
```

### 4. 验证 embedding 质量

```python
# 相似问题应该返回高相似度
import numpy as np
from app.services.embedding import get_embedding_service
es = get_embedding_service()
v1 = es._embed_mock(["头痛怎么办"])
v2 = es._embed_mock(["头疼怎么处理"])  # 同义不同字
v3 = es._embed_mock(["胃痛怎么办"])  # 不同主题
print(f"头痛 vs 头疼: {np.dot(v1[0], v2[0]):.3f}")  # 应该较高
print(f"头痛 vs 胃痛: {np.dot(v1[0], v3[0]):.3f}")  # 应该较低
# mock 模式:同义不同字哈希后可能不接近,这就是 mock 的局限
```

---

## 📚 延伸阅读

- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki) — 向量检索库
- [Sentence-BERT](https://www.sbert.net/) — 语义向量模型
- [BGE 系列](https://huggingface.co/BAAI/bge-small-zh-v1.5) — 中文向量强
- [RAG 综述](https://arxiv.org/abs/2312.10997) — 学术综述
- [Hybrid Search](https://www.pinecone.io/learn/series/faiss/hybrid-search/) — 混合检索

---

## 📝 总结

本项目 RAG 实现是一个**轻量、可生产、零起步成本**的方案:

- **起步零依赖**: `mock` Embedding 不下任何模型就能跑
- **渐进升级**: 改一行 `.env` 就能切到真 Embedding
- **完整闭环**: 文档 → 索引 → 检索 → 上下文 → LLM 响应
- **16 条起步**: 满足演示和小型生产,可平滑扩到数千条

核心代码 400 行,涵盖了 RAG 工业实践的所有关键环节。
