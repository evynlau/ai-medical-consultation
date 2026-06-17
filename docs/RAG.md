# RAG 检索增强生成 — 实现文档

> 本项目 RAG 模块位于 `backend/app/services/rag_service.py` + `backend/app/services/embedding.py` + `scripts/init_kb.py`,约 400 行,实现了 **"医学知识向量检索 + 可选关键词加权 + LLM 上下文组装"** 的完整链路。
>
> 与旧版 RAG.md 的差异:本版对齐了 `EMBEDDING_DIM=384` 默认、119 篇知识库现状、`hybrid_search` 关键词加权为可选行为、admin 与公开知识库 API 区分。

---

## 📐 架构总览

```
                          ┌──────────────────────────┐
                          │       RAG 架构全景        │
                          └──────────────────────────┘

   ═══ 离线(知识库构建) ═══                              ═══ 在线(实时检索) ═══

   knowledge_base/*.md                                      用户提问
   (Markdown 文档)                                              │
   ├ diseases/   18                                            │
   ├ drugs/      83                                            │
   ├ examinations/ 8                                           │
   └ guidelines/ 10                                            ▼
       │                                                MedicalAgent
       │ parse_markdown()                              .analyze_symptoms()
       ▼                                                       │
   ┌──────────┐   ┌──────────────────┐                RAGService
   │ SQLite   │──▶│ Embedding Service │                    │
   │(Knowledge│   │ (向量化)         │                    │
   │ model)   │   │ mock/local/openai│                    │
   └──────────┘   └────────┬─────────┘                    │
       │                    │                              │
       │  text = title +    │                              │
       │  tags + content    │                              │
       ▼                    ▼                              │
   ┌─────────────────────────────────┐                    │
   │ FAISS IndexFlatIP(dim=384)      │                    │
   │ + metadata.json(原始文档)        │                    │
   │ 保存在 backend/data/faiss_index/│                    │
   └────────┬────────────────────────┘                    │
            │                                               │
            │ 启动 lifespan 阶段                          │
            ▼                                               │
       RAGService 单例 ◄────────────────────────────────────┘
            │
            │ 4. hybrid_search(query, keywords?, top_k=5)
            │    ├─ vector search (L2 归一化 + 内积 = 余弦)
            │    └─ 关键词加权 (keywords 传入时启用:0.7 向量 + 0.3 关键词)
            ▼
       Top-K 相关知识
            │
            ▼
   拼到 LLM Prompt:
   【相关医学知识参考】
   1. 《高血压》 (disease)   <截取 500 字>   [score=0.85]
   2. 《冠心病》 (disease)   <截取 500 字>   [score=0.72]
            │
            ▼
       LLM 生成回复(基于检索结果,降低幻觉)
```

---

## 🧩 三大核心组件

### 1. `backend/app/services/embedding.py` — Embedding 服务

把文本转成向量。**三种 provider 行为不同**:

| Provider | 原理 | 依赖 | 适用 |
|---|---|---|---|
| `mock`(默认) | 字符 n-gram 哈希 + 符号随机化 + L2 归一化 | 零依赖 | 演示、CI、零资源场景 |
| `local` | `sentence-transformers.SentenceTransformer` | 首次下载 ~120MB | 本地语义检索 |
| `openai` | `text-embedding-3-small` | API Key | 生产质量 |

**关键实现**(`_embed_mock`):
```python
def _embed_mock(self, texts: List[str]) -> np.ndarray:
    vecs = []
    for text in texts:
        v = np.zeros(self.dim, dtype="float32")    # dim=384
        for token in self._tokenize(text):         # 中英混合分词
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % self.dim
            sign = 1.0 if (h & 1) else -1.0
            v[idx] += sign
        # L2 归一化
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        vecs.append(v)
    return np.stack(vecs)
```

**关键设计**:
- **中英混合分词**:中文按字符切(无 jieba 依赖),英文按连续字母/数字切
- **固定维度 384**:保证 mock 和 local/openai 输出形状一致,FAISS 接口可互换
- **`_embed_openai` 分批**:batch_size=100,避免单次请求过大

> 运行时**异步**:所有 `embed()` 都返回 `np.ndarray`(不是协程),`rag_service` 在内部用 `_run_async` 把它桥接到 uvicorn 的事件循环,避免与 uvloop 冲突(详见 `rag_service._run_async`)。

---

### 2. `backend/app/services/rag_service.py` — RAG 核心

#### 离线构建 + 在线检索 双模式

| 方法 | 用途 | 调用方 |
|---|---|---|
| `initialize()` | 启动时加载已有索引 | `lifespan` 阶段 |
| `build_index(docs)` | 从零构建/重建 FAISS 索引 | `init_kb.py`、admin 增删改查知识 |
| `search(query, top_k)` | 纯向量检索 | 通用 |
| `hybrid_search(query, keywords?, top_k)` | 向量 + 关键词加权(可选) | `MedicalAgent.analyze_symptoms` 实际只传 query,等价于 `search` |

#### 关键实现(`search`)
```python
def search(self, query, top_k=5, score_threshold=None):
    # 1) 自动加载索引
    if self.index is None or self.index.ntotal == 0:
        self.initialize()
        if self.index is None or self.index.ntotal == 0:
            return []

    # 2) 嵌入查询(独立线程跑 async,绕开 uvloop)
    q_vec = self._run_async(self.embedding.embed([query]))
    q_vec = np.array(q_vec).astype("float32")
    norm = np.linalg.norm(q_vec)
    if norm > 0:
        q_vec = q_vec / norm                # 归一化

    # 3) 阈值(默认 settings.RAG_SCORE_THRESHOLD = 0.2)
    threshold = score_threshold if score_threshold is not None else settings.RAG_SCORE_THRESHOLD

    # 4) 召回 top_k * 2(给关键词加权留排序空间)
    distances, indices = self.index.search(q_vec, min(top_k * 2, self.index.ntotal))

    # 5) 过滤 + 组装结果
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(self.documents):
            continue
        if dist < threshold:
            continue
        doc = self.documents[idx]
        results.append({... "score": float(dist) ...})
    return results[:top_k]
```

#### 关键实现(`hybrid_search`,关键词加权)
```python
def hybrid_search(self, query, keywords=None, top_k=5):
    # 1) 先做向量召回(top_k * 2)
    vector_results = self.search(query, top_k=top_k * 2)
    if not vector_results:
        return []

    # 2) 关键词加权 (仅在 keywords 不为 None 时启用)
    if keywords:
        for r in vector_results:
            content = (r.get("content", "") + r.get("title", "")).lower()
            matches = sum(1 for kw in keywords if kw.lower() in content)
            r["keyword_score"] = matches / max(len(keywords), 1)
            r["combined_score"] = r["score"] * 0.7 + r["keyword_score"] * 0.3
        vector_results.sort(key=lambda x: x.get("combined_score", x["score"]), reverse=True)

    return vector_results[:top_k]
```

> 注意:**`MedicalAgent.analyze_symptoms` 调 `hybrid_search` 时没有传 `keywords`**,所以走的就是纯向量路径。关键词加权是为「调用方想加白名单关键词」留的接口。

#### 为什么用 `IndexFlatIP`(内积)而不是 `IndexFlatL2`(欧氏距离)?
- 向量已 L2 归一化 → 内积 = 余弦相似度
- 余弦对向量长度不敏感,关注方向(语义),更符合文本检索直觉
- 精确检索(`IndexFlatIP`)在 119 条 ~ 数千条规模上延迟毫秒级

#### 持久化结构
```
backend/data/faiss_index/
├── index.faiss       # FAISS 二进制索引
└── metadata.json     # 原始文档数组(对应索引 id)
```

`build_index` 完成后,`lifespan` 启动时 `initialize()` 自动加载,无需手动 hot-reload。

---

### 3. `scripts/init_kb.py` — 知识库初始化

把 `knowledge_base/*.md` 灌进数据库 + 构建 FAISS 索引。

**Markdown 解析规则**(`parse_markdown`):
```python
# 第一个 "# 标题"       → knowledge.title
# "## 二级标题"         → 在 content 中降级为 "### 二级标题"
# "- 列表项"            → content 一行
# 列表项第一个词(1-12字)→ 自动作为 tag
# 空行 / 其他行          → content 一行
```

**入库流程**:
1. 遍历 `knowledge_base/{diseases,drugs,examinations,guidelines}/*.md`
2. 每篇 MD → `parse_markdown()` → `{title, content, tags}`
3. SQL 查重(`title + category` 唯一)
4. 新条目 `INSERT INTO knowledge`
5. 全部新文档 → `rag_service.build_index()`

**幂等性**:重复执行不会重复插入(查重逻辑)。`init_kb.py` 退出码 0 即视为成功。

> **注意**:`init_kb.py` 只灌四个子目录;根目录的 `医保常用药品列表.md` / `医保药品速查表.md` **不会**被它写入。如需,走 API 走后台。

---

## 🔄 端到端数据流

### 离线阶段(一次或知识更新时)

```
knowledge_base/diseases/普通感冒.md
        │
        │ parse_markdown()
        ▼
{ "title":"普通感冒",
  "content":"感冒多为病毒感染,5-7 天可自愈...",
  "tags":"病毒,感染,自愈",
  "category":"disease" }
        │
        │ INSERT INTO knowledge
        ▼
SQLite row(id=1, title=..., content=..., category=...)
        │
        │ build_index([{id:1, ...}, {id:2, ...}, ...])
        ▼
FAISS IndexFlatIP(dim=384) + metadata.json
backend/data/faiss_index/
```

### 在线阶段(每次问诊)

```
用户:"头痛 3 天,伴有低烧"
  │
  │ MedicalAgent.analyze_symptoms(symptoms)
  │   ├─ 1. detect_emergency(URGENT_REGEX)  ← 关键字紧急识别
  │   ├─ 2. rag.hybrid_search(query, top_k=5)  ← 不传 keywords = 纯向量
  │   │     ├─ embedding.embed(["头痛 3 天..."]) → (1, 384) 向量
  │   │     ├─ FAISS index.search(q_vec, k=10) → 余弦距离
  │   │     ├─ 过滤 dist < RAG_SCORE_THRESHOLD (0.2)
  │   │     └─ 返回 top-5
  │   ├─ 3. 拼到 LLM Prompt
  │   └─ 4. llm.chat() → 解析 JSON {reply, urgency_level, ...}
  ▼
返回 JSON 给前端,同时:
  - 写回 consultation(urgency_level / recommended_department)
  - 插入 assistant 消息(包含源知识 source_knowledge)
```

---

## ⚙️ 配置项(`backend/.env`)

```bash
# Embedding 引擎
EMBEDDING_PROVIDER=mock                                       # mock | local | openai
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384                                              # 跟 Embedding 模型输出维度对齐

# RAG 检索参数
RAG_TOP_K=5                                                   # 召回数量
RAG_SCORE_THRESHOLD=0.2                                       # 相似度阈值,低于此分数的丢弃
```

**生产推荐配置**:
```bash
# 方案 A:本地(无需 Key)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DIM=512
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.3

# 方案 B:云端
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.3
```

**中文强向量推荐**:
- `BAAI/bge-small-zh-v1.5`(512 维,中文 SOTA,小)
- `BAAI/bge-large-zh-v1.5`(1024 维,更准)
- `DMetaSoul/sbert-chinese-medical-voc-distil`(社区医学微调)

---

## 📊 知识库结构

```
knowledge_base/
├── diseases/        → category="disease"      (18 篇,疾病)
├── drugs/           → category="drug"         (83 篇,药品)
├── examinations/    → category="examination"  ( 8 篇,检查)
├── guidelines/      → category="guideline"    (10 篇,临床指南)
├── 医保常用药品列表.md   ← ⚠️ init_kb.py 不会自动灌
└── 医保药品速查表.md     ← ⚠️ init_kb.py 不会自动灌
```

**当前规模**:**119 篇** + 2 张未灌入的医保表(共 121 个 MD)。

**每篇 Markdown 规范**:
- 第一个 `#` 标题 = `title`
- 列表项首词(1-12 字) = 自动 `tags`
- 其余 = `content`

**扩展方式**(3 种):
1. **文件**:放 `.md` 到对应子目录,跑 `init_kb.py`(注意:仅 4 个子目录)
2. **API(管理员)**: `POST /api/v1/admin/knowledge` + 自动 reindex
3. **管理后台 UI**: `/admin/knowledge` → 新增/编辑 → 自动 reindex

---

## 🛠️ 常见操作

### 重建索引(知识变更后)

```bash
# 方式 1:重新 init(也会写 DB)
python scripts/init_kb.py

# 方式 2:仅重建索引(不写 DB,适合切了 Embedding 后)
curl -X POST http://localhost:8000/api/v1/admin/knowledge/reindex \
  -H "Authorization: Bearer $TOKEN"

# 方式 3:管理后台 UI
# /admin/knowledge → "重建索引" 按钮
```

> ⚠️ 改了 `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` 后必须重建索引,否则维度对不上会报错。

### 切换到真 Embedding

```bash
# .env
EMBEDDING_PROVIDER=local    # 或 openai

# 重建索引(用新 Embedding 重新向量化所有文档)
python scripts/init_kb.py
# 或仅重建索引(不重写 DB):
curl -X POST http://localhost:8000/api/v1/admin/knowledge/reindex -H "Authorization: Bearer $TOKEN"
```

### 添加新知识(代码方式)

```python
from app.models.knowledge import Knowledge
from app.core.database import AsyncSessionLocal
import asyncio
from sqlalchemy import select

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
        # 重建索引(从 DB 全量读)
        from app.services.rag_service import get_rag_service
        rag = get_rag_service()
        rows = (await db.execute(select(Knowledge))).scalars().all()
        docs = [{"id": r.id, "title": r.title, "content": r.content,
                 "category": r.category, "tags": r.tags or "", "source": r.source or ""}
                for r in rows]
        rag.build_index(docs)

asyncio.run(add_kb())
```

### 调 RAG 检索参数

```python
from app.services.rag_service import get_rag_service
rag = get_rag_service()
# 纯向量
results = rag.hybrid_search(query="头痛", top_k=10)
# 向量 + 关键词加权
results = rag.hybrid_search(query="头痛", keywords=["偏头痛", "紧张性头痛"], top_k=10)
for r in results:
    print(f"{r['title']}: combined={r.get('combined_score', r['score']):.3f}")
```

---

## 🚀 可扩展点

### 1. 升级 Embedding(替换 `mock`)
- **本地**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`(多语言)
- **中文强**: `BAAI/bge-small-zh-v1.5` / `BAAI/bge-large-zh-v1.5`
- **医疗专用**: `DMetaSoul/sbert-chinese-medical-voc-distil`(社区微调)
- **云端**: OpenAI `text-embedding-3-small` / `-large`

### 2. 升级到混合检索 + Rerank
**当前**: 向量召回 + 可选关键词加权
**升级路径**: 加 BM25 召回 + Cross-Encoder Reranker

```python
# 升级版 hybrid_search 思路
def hybrid_search(self, query, top_k=5):
    # 1) 向量召回(语义)
    vec = self.search(query, top_k=top_k * 3)
    # 2) BM25 召回(关键词) — 新增
    bm25 = self.bm25_search(query, top_k=top_k * 3)
    # 3) RRF 融合
    rrf = lambda r, rank: 1 / (60 + rank)
    fused = self.rrf_fuse(vec, bm25)
    # 4) Reranker 精排(可选)
    # fused = self.rerank(query, fused[:20])[:top_k]
    return fused[:top_k]
```

### 3. 知识分块(Chunking)
**当前**: 一篇 MD = 一个文档
**升级**: 按 ~500 字/块、50 字 overlap 拆,提高检索粒度。

### 4. 多向量(ColBERT 式)
每个 token 一个向量,精细匹配(成本高,通常 Reranker 阶段已够用)。

### 5. 知识图谱增强
把医学概念(疾病 ↔ 症状 ↔ 药品)建成图,检索时既走向量也走图遍历。

---

## 🔬 性能特征

### 当前实现

| 维度 | 数值 |
|---|---|
| 文档规模 | 119 条(可平滑扩到数千,FAISS `IndexFlatIP` 万级毫秒级) |
| Embedding 维度 | 384(mock)/ 384-1536(local/openai) |
| 单次检索延迟 | mock: <1ms / local: ~50ms / openai: ~200ms |
| 内存占用 | mock: 几乎 0 / 1000 docs: ~1.5MB |
| 并发支持 | FAISS 线程安全,Embedding 单例共享 |

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
print(f"原始文档数: {len(rag.documents)}")
```

### 2. 直接看检索结果

```python
results = rag.search("头痛", top_k=5)
for r in results:
    print(f"[{r['score']:.3f}] {r['title']} ({r['category']})")
```

### 3. 启动后端时观察 RAG 日志
```
✅ 加载 RAG 索引: 119 条
# 或
开始向量化 119 条知识...
✅ RAG 索引构建完成: 119 条, dim=384
```

### 4. 验证 Embedding 质量

```python
import numpy as np
from app.services.embedding import get_embedding_service
es = get_embedding_service()
v1 = es._embed_mock(["头痛怎么办"])
v2 = es._embed_mock(["头疼怎么处理"])   # 同义不同字
v3 = es._embed_mock(["胃痛怎么办"])     # 不同主题
print(f"头痛 vs 头疼: {np.dot(v1[0], v2[0]):.3f}")  # mock 模式可能不高(哈希局限)
print(f"头痛 vs 胃痛: {np.dot(v1[0], v3[0]):.3f}")
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

- **起步零依赖**:`mock` Embedding 不下任何模型就能跑
- **渐进升级**:改一行 `.env` 就能切到真 Embedding
- **完整闭环**:文档 → 索引 → 检索 → 上下文 → LLM 响应
- **119 条起步**:满足演示和小型生产,可平滑扩到数千条

核心代码约 400 行,涵盖 RAG 工业实践的所有关键环节。
