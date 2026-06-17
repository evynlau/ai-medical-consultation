# AI 智能问诊系统 — 深度项目分析

> 仓库:`/home/evynlau/桌面/AI-Agent/AI智能问诊系统`
> 后端 ~4700 行 Python,前端 ~5100 行 Vue/JS,**1 个在线推理模型**(xrv DenseNet121),**2 个离线训练脚本**(自训练 ResNet50 + 医院专属多标签),3 种 LLM provider,3 种 OCR 引擎,完整管理后台

---

## 0. 一句话总结

一个**多模态医疗 AI 工作台**,把 **LLM 对话 + 知识库 RAG + 胸片 X-ray 多分类 + 处方/报告 OCR + 医生人工接管** 五个能力塞进同一个 FastAPI + Vue 3 系统。结构上比 README 描述的"LLM+Agent+RAG"复杂得多,实际上跑着 **torchxrayvision DenseNet121**(在线唯一推理引擎) + 两个**离线训练脚本**(`train_pneumonia.py` 二分类 / `train hospital_model.py` 多标签微调)。

---

## 1. 项目实际规模(与 README 对比)

README 自我定位是 "LLM+Agent+RAG",但实际仓库还包含:

| 模块 | README 提到? | 实际代码 | 关键文件 |
|---|---|---|---|
| LLM 问诊对话 | ✅ | 565 行 + 310 行 agent | `llm_service.py`、`medical_agent.py` |
| RAG 知识库检索 | ✅ | 181 + 114 行 | `rag_service.py`、`embedding.py` |
| 多轮问诊 + 紧急识别 | ✅ | 模型 6 个,API 1 套 | `consultation.py`、`agent.py` |
| **胸片 X-ray 18 病理多分类** | ❌ 完全没提 | **436 行 + 301 行 API** | `xrv_service.py`、`imaging.py` |
| **Grad-CAM/HiResCAM 热力图** | ❌ | 同上 | `xrv_service.py` 内 |
| **PSPNet 肺部分割** | ❌ | 同上 | `xrv_service.py` 内 |
| **离线训练:自训练 ResNet50** | ❌ | 训练脚本 1 个(314 行) | `train_pneumonia.py` |
| **离线训练:医院专属多标签** | ❌ | 训练脚本 1 个(647 行) | `train hospital_model.py` |
| **OCR 处方/报告识别** | ❌ | 230 行 service + 214 行 API | `ocr_service.py`、`ocr.py` |
| **结构化 LLM 二次解析** | ❌ | 内嵌 | `ocr.py` 内 |
| 管理后台 6 页 | ✅ | 6 个 .vue 文件 | `admin/*.vue` |
| 影像分析管理 | ❌(本次新增) | 复用 `Imaging/History.vue` | `/admin/imaging` |
| WebSocket 流式对话 | ❌ | 128 行 | `ws/chat.py` |
| Mock LLM 引擎 | ❌ 但有用 | 200+ 行,完整模板 | `llm_service.py` 内 |
| **思考型模型适配** | ❌ | 100+ 行清洗逻辑 | `llm_service.py._clean_reply` |

**结论**:实际是**六合一系统**(LLM+RAG+影像+OCR+管理后台+WebSocket),README 旧版只描述了 3/6。

---

## 2. 顶层架构图

```
                    ┌──────────────────────────────────────┐
                    │         Vue 3 前端 (Element Plus)     │
                    │  Chat | History | Knowledge | OCR |   │
                    │  Imaging | Admin(/admin 后台)         │
                    └────────────────┬─────────────────────┘
                                     │ Axios + JWT
                                     ▼
                    ┌──────────────────────────────────────┐
                    │      FastAPI 入口 (main.py)           │
                    │  /api/v1/* + /api/ws/chat + /docs    │
                    └────────────────┬─────────────────────┘
                                     │
        ┌────────────┬───────────────┼───────────────┬──────────────┐
        ▼            ▼               ▼               ▼              ▼
   ┌─────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐
   │ Agent   │ │  LLM     │ │    RAG       │ │ Imaging  │ │    OCR       │
   │Layer    │ │ Service  │ │   Service    │ │ Service  │ │   Service    │
   │(395行)  │ │ (565行)  │ │   (181行)    │ │ (290行)  │ │   (230行)    │
   └─────────┘ └──────────┘ └──────────────┘ └──────────┘ └──────────────┘
        │            │              │                │              │
        │       ┌────┴────┐    ┌────┴────┐     ┌─────┴─────┐        │
        │       │  OpenAI │    │ FAISS   │     │torchxray- │        │
        │       │  Compat │    │IndexFlat│     │  vision   │        │
        │       │  + Mock │    │   IP    │     │ DenseNet  │        │
        │       │  + Ollama│   └─────────┘     │  +PSPNet  │        │
        │       └─────────┘         │          └───────────┘        │
        │                          ▼                                 │
        │                    ┌─────────┐      ┌──────────────────┐  │
        │                    │Embedding│      │ 多模态 LLM       │  │
        │                    │  3 种   │      │ (vision OCR)     │  │
        │                    │ provider│      │ 或 Tesseract     │  │
        │                    └─────────┘      └──────────────────┘  │
        │                                                         │
        ▼                                                         ▼
   ┌──────────────────────────────────────────────────────────────┐
   │   SQLite (aiosqlite) + SQLAlchemy 2.0 async                  │
   │   User | Consultation | Message | Knowledge | OcrRecord |    │
   │   ImagingAnalysis | DoctorAnnotation | ImagingModel         │
   └──────────────────────────────────────────────────────────────┘
```

---

## 3. 模块逐一拆解

### 3.1 LLM Service(最成熟的部分,565 行)

**位置**:`backend/app/services/llm_service.py`

**架构**:

```
LLMService
  ├── provider: "openai" (兼容协议,实际归一 ollama/openai/mock)
  │     ├── openai: AsyncOpenAI 客户端(Ollama 走 base_url=http://localhost:11434/v1 自动归一)
  │     └── mock: 内置规则引擎 + 200 行模板
  ├── chat(): 主入口,统一处理流式/非流式/错误降级
  ├── _clean_reply(): 清洗"思考型模型"的 planning 残留
  └── _extract_final_answer(): 从 reasoning 字段救回答案
```

**亮点 1:思考型模型适配**(全网最稀缺的能力)

Ollama 上很多 MoE 思考型模型只输出 `reasoning` 不输出 `content`。本项目做了三层降级:

```python
# Layer 1:正常 content 直接用
content = message.content

# Layer 2:content 空,从 reasoning 提取
if not content:
    content = self._extract_final_answer(reasoning)

# Layer 3:_clean_reply 剥掉思考型模型的残留标记
content = self._clean_reply(content)
# 例如剥离 "Check against Constraints" / "Draft JSON" / "Map to JSON Schema" / "Step 1. 2. 3." 等
```

`_extract_final_answer` 的优先级很有意思:

1. reasoning 中内嵌的 ` ```json {…} ``` ` 代码块(最准确)
2. reasoning 中的纯 JSON 对象
3. "最终答案/Final Answer/输出如下"标记后的内容
4. 按中文密度 + 长度过滤,挑最像中文医学答案的段落
5. 兜底取最后 800 字

**亮点 2:Mock 引擎不只是占位**

`_mock_general_chat` 是一个完整的、症状感知的对话模板:
- 接收完整 `messages` 历史感知上下文
- 极短回答(<8 字)走 followup 流程
- 11 种症状关键词各自匹配专门回复(感冒/头痛/发热/咳嗽/腹痛/胸痛/血压/过敏/失眠/饮食/用药)
- `_mock_followup` 按对话轮次动态决定下一步该问什么(持续多久?伴随症状?既往史?用药史?)
- `_mock_triage` 和 `_mock_symptom_analysis` 生成完整 JSON

意味着**零 Key 也能完整体验整套流程**,适合演示和 CI。

**亮点 3:防止 LLM 把思考过程泄露给前端**

```python
cut_markers = [
    r"\n\s*\d+\.\s+\*\*Draft\b",   # 4. **Draft - Section by Section
    r"\n\s*Check against Constraints[:：]?",
    r"\n\s*Draft JSON",
    ...
]
# 启发式:残留长度 < 50 字且无医学关键词 → 整段丢弃
```

### 3.2 Medical Agent(医疗问诊逻辑,310 行)

**位置**:`backend/app/agents/medical_agent.py`

**三个核心能力**:

1. **`analyze_symptoms()`** — 结构化症状分析,输出 JSON `{reply, urgency_level, needs_urgent_care, possible_causes, suggested_examinations, department, self_care_tips, reference_sources}`
2. **`chat()`** — 多轮对话,带 RAG + 历史 + 紧急检测
3. **`triage()`** — 轻量分诊(只输出科室+紧急度)

**关键设计**:

- **紧急关键词硬编码**:30+ 中文关键词(胸痛/呼吸困难/大出血/昏迷/中风/剧烈头痛/自杀…)走正则兜底,**LLM 不参与紧急判定**,确保即使 LLM 出错也不会漏掉紧急情况
- **`detect_emergency` 覆盖结果**:LLM 输出 `urgency_level=3` 但关键词命中,强制覆盖为 4
- **JSON 解析三级回退**:直接 parse → ```json 代码块 → 第一个 `{...}` 块 → 兜底 dict
- **RAG 上下文组装**:`【相关医学知识参考】` 块 + Top-5 知识 + 来源追踪

### 3.3 RAG Service(181 行)

**位置**:`backend/app/services/rag_service.py` + `embedding.py`

**架构**:

```
RAGService
  ├── 离线: build_index(docs) → FAISS IndexFlatIP(内积=余弦) + metadata.json
  ├── 在线: search(query, top_k) → 向量召回
  ├── hybrid_search(): 向量 × 0.7 + 关键词 × 0.3 综合排序
  └── 持久化: ./data/faiss_index/{index.faiss, metadata.json}
```

**Embedding 三档**:
- `mock` — 字符 n-gram hash(零依赖,演示用)
- `local` — sentence-transformers MiniLM(下载 ~120MB,本地语义)
- `openai` — text-embedding-3-small(生产)

**踩坑修复 — uvicorn uvloop 兼容**:

RAG 启动时(`warmup_rag`)和 OCR service 都用**独立线程跑 `asyncio.run`** 绕过 uvloop 冲突。这是一个不显眼但实战必备的 hack。

### 3.4 影像分析(整套独立子系统,这是 README 旧版没提到的最大惊喜)

**位置**:`backend/app/services/imaging/` + `api/v1/imaging.py`

**在线推理 + 两个离线训练脚本**:

| 模型 | 来源 | 用途 | 状态 |
|---|---|---|---|
| **torchxrayvision DenseNet121-res224-chex** | 官方预训练 | **18 病理多分类 + Grad-CAM/HiResCAM**(11 类为 chex 权重有训练) | ✅ **当前唯一在线推理** |
| **自训练 ResNet50** (`pneumonia_resnet50.pth`) | `train_pneumonia.py` 训练 | 肺炎 NORMAL/PNEUMONIA 二分类 | ⚠️ 离线脚本,未接入 |
| **医院专属多标签** | `train hospital_model.py` 训练 | xrv 微调 → 自定义 11 类 | ⚠️ 离线脚本,未接入 |
| **PSPNet** | torchxrayvision baseline | 14 类解剖结构分割 | 用于限制 Grad-CAM 在双肺内 |

**关键代码片段** `xrv_service.py:138-198`:

```python
def predict(self, image):
    features = self._xrv_model.features(x)         # (1, 1024, 7, 7)
    pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
    logits = self._xrv_model.classifier(pooled)
    probs = torch.sigmoid(logits[0]).cpu().numpy()

    # 用 xrv 官方 op_threshs (PPV=80% 工作点)
    thresholds = self._get_thresholds()

    # 主诊断 = 阳性中 "概率/阈值比" 最高的
    main = max(positive_results, key=lambda r: r["probability"] / (r["threshold"] + 1e-8))
```

**HiResCAM 实现**(`xrv_service.py:252-299`):

```python
features = self._xrv_model.features(x)
features.retain_grad()
pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
logits = self._xrv_model.classifier(pooled)

logits.backward(gradient=one_hot)
cam = (features * features.grad).sum(dim=1, keepdim=True)  # HiResCAM 公式
cam = F.interpolate(cam, size=image.size[::-1], mode="bilinear")
```

**PSPNet 肺部分割限制 Grad-CAM 范围**(`xrv_service.py:240-241`):

```python
# 仅保留双肺区域的热力图,避免背景干扰
lung_mask = (probs[4] + probs[5]) > 0.5   # Left Lung + Right Lung
cam_masked = cam * lung_mask
```

**接口**:`POST /api/v1/imaging/pneumonia/analyze`
- 输入:胸片 PNG/JPG(≤10MB)
- 输出:18 病理的 prob/threshold/positive,主诊断,Grad-CAM overlay PNG(base64),可选 target_classes 子集
- 持久化到 `imaging_analysis` 表,支持医生标注(agreement/correct_label)
- 医生标注端点:`POST /api/v1/imaging/{id}/annotate`,列表:`GET /api/v1/imaging/{id}/annotations`

### 3.5 OCR Service(230 行)

**位置**:`backend/app/services/ocr_service.py` + `api/v1/ocr.py`

**三层引擎自动降级**(由 `OCR_ENGINE` 控制):

```
vision (多模态 LLM: llama3.2-vision / qwen2-vl / GPT-4V)
   ↓ 失败
tesseract (本地,需 apt install tesseract-ocr-chi-sim)
   ↓ 失败
mock (返回预设的"张三高血压处方"+"李四糖尿病报告"演示文本)
```

**两步管线**:

1. **OCR 引擎** 把图片转成原始文本(保留格式、异常标记、表格)
2. **LLM 二次结构化** — 用 prompt 把原始文本按"处方"或"检查报告"分类并提取字段(JSON)

```python
# OCR 完成后
structured = await _structure_with_llm(llm, raw_text, image_type)
# 返回:
# 处方:{patient, hospital, doctor, diagnosis, medications[{name,dose,quantity,frequency,route}], instructions}
# 报告:{patient, items[{name,result,unit,reference_range,abnormal}], summary}
```

**临床价值**:这等于把"医院拍的报告照片"变成可机读的 JSON,可直接喂回问诊做上下文(`pendingContext` in chat store)。

### 3.6 管理后台(后端 admin.py + 前端 6 个 .vue)

**前端页面**(共 1300 行 Vue):

| 页面 | 行数 | 功能 |
|---|---|---|
| `AdminLayout.vue` | 159 | 左侧菜单 + 顶部用户信息 |
| `Dashboard.vue` | 211 | 8 张指标卡 + 7 日趋势 + KB 分布 |
| `Consultations.vue` | 275 | 全平台问诊 + 医生回复表单 |
| `Emergency.vue` | 122 | urgency≥4 列表 |
| `KnowledgeAdmin.vue` | 197 | CRUD + 重建索引 |
| `Users.vue` | 199 | 角色管理 |

**Dashboard 后端聚合查询**:

```python
# admin.py:39-89
total_users / total_consultations / total_knowledge
today_new / week_new
urgent_total / urgent_pending
active_count / closed_count
kb_by_category (聚合查询)
trend_7d (for i in 7: 范围 count)
```

### 3.7 WebSocket 实时对话(128 行)

**位置**:`backend/app/api/ws/chat.py`

简化版流式 — 把 LLM 完整回复切成 12 字一个 chunk 推送,模拟流式效果(实际不是真正的 streaming completion)。前端通过 `/api/ws/chat` 接收 `{type: "delta" | "done" | "user_saved"}` 三种事件。

### 3.8 数据模型(7 张表)

```
users ──┬── consultations ── messages (user/assistant/system/doctor)
        └── (独立)

imaging_analysis ── doctor_annotation (1:N)
                   └── imaging_model (模型注册表)

knowledge (知识条目)             ← Markdown 自动同步(共 119 篇)
ocr_records (OCR 历史)            ← 处方/报告(含原图)
```

**`Message` 表的 role 设计**:`user / assistant / system / doctor` 四种,**`message_type` 区分** `text / analysis / doctor_reply`,配合 `source_knowledge`(JSON 数组)和 `urgency_level`,完整保留每条消息的来源链路。

---

## 4. 数据流走查(端到端)

### 4.1 典型患者问诊流程

```
1. POST /consult {chief_complaint: "胸痛 1 小时"}
   → 创建 consultation,role=system 消息
   → agent.chat() 拉历史(空),RAG 检索 → LLM 回复
   → 返回完整 consultation 对象

2. POST /consult/{id}/messages {content: "持续压榨样"}
   → 拉历史 → RAG → agent.chat() 多轮推理
   → 检测紧急关键词 → 强制 urgency_level=4
   → 更新 cons.urgency_level
   → 返回 ai_msg + 最新 cons

3. POST /agent/analyze {symptoms, consultation_id}
   → agent.analyze_symptoms() 结构化分析
   → 同步结果:cons.urgency_level, cons.recommended_department
   → 插入 role=assistant, message_type=analysis 消息
   → 返回 JSON 报告

4. (可选)医生在管理后台 POST /admin/consultations/{id}/reply
   → 插入 role=doctor, message_type=doctor_reply 消息
   → cons.status = "closed"
```

### 4.2 影像分析流程

```
1. POST /imaging/pneumonia/analyze (multipart: file)
   → 医生权限校验
   → XRVAnalysisService.predict_from_bytes_with_gradcam()
     ├─ 加载 torchxrayvision DenseNet121-chex
     ├─ 加载 PSPNet 肺部分割
     ├─ 11 病理概率 + 主诊断
     ├─ 为每个目标病理生成 HiResCAM
     ├─ PSPNet mask 限制到双肺
     └─ 返回 base64 PNG (overlay + raw)
   → 持久化到 imaging_analysis
   → 返回完整 JSON

2. (可选) POST /imaging/{id}/annotate {annotation, agreement, correct_label}
   → 插入 doctor_annotation 记录
   → 更新 imaging_analysis.annotation/agreement/correct_label
```

### 4.3 OCR → 问诊的链路

```
1. POST /ocr/upload (multipart: file, image_type)
   → 保存到 ./data/ocr_uploads/
   → OCR 引擎识别 → 原始文本
   → LLM 结构化为 JSON
   → 持久化到 ocr_records

2. 前端拿到 structured_data 后,通过 chat store 的 pendingContext
   → 自动发起一次"基于这份报告的咨询"
```

---

## 5. 三个值得称道的工程细节

### 5.1 异步 + uvloop 的破局

**问题**:uvicorn 用 uvloop 时,在已有 event loop 里 `asyncio.run()` 会抛 `RuntimeError`。RAG service 在 lifespan 阶段(`async with AsyncSessionLocal`)被调用,如果它内部用 `asyncio.run(embed(...))` 就会炸。

**方案**(`rag_service.py:_run_async`):
```python
def _run_async(self, coro):
    result = {"value": None, "error": None}
    def _call():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as e:
            result["error"] = e
    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=180)
    if result["error"]: raise result["error"]
    return result["value"]
```

**OCR service 用同样的 pattern**。这是一个实战级 hack,在任何 FastAPI + uvloop 项目里都通用。

### 5.2 患者画像自动注入 prompt

**位置**:`medical_agent.py:_build_system_prompt`

```python
if user_context:
    ctx = []
    if user_context.get("age"):       ctx.append(f"年龄:{user_context['age']}")
    if user_context.get("gender"):     ctx.append(f"性别:{user_context['gender']}")
    if user_context.get("allergies"):  ctx.append(f"过敏史:{user_context['allergies']}")
    if user_context.get("chronic_diseases"): ctx.append(f"慢性病:{user_context['chronic_diseases']}")
    if ctx:
        base += "\n\n【患者基本信息】\n" + "\n".join(ctx)
```

`User` 表里的 `age / gender / allergies / chronic_diseases` 在每次 `agent.chat()` 时被自动注入到 system prompt。这是把"数据模型 → 业务行为"的连接做得最自然的一处。

### 5.3 紧急判定双保险

LLM 可能误判(如把"胸痛"判成 urgency=2),所以:

1. **关键词兜底**:`URGENT_REGEX = re.compile("|".join(URGENT_KEYWORDS))` 30+ 关键词命中即强制
2. **结果覆盖**:`if is_emergency and not result.get("needs_urgent_care"): ... result["urgency_level"] = max(..., 4)`

紧急情况永远不被 LLM 误判压低,这是医疗 AI 的生命线。

---

## 6. 不足与可改进点

| 问题 | 影响 | 改进建议 |
|---|---|---|
| **Mock Embedding 无语义能力** | 切到 `mock` 模式后 RAG 检索质量骤降 | 默认改 `local`(MiniLM 120MB),或不开放 mock 给生产 |
| **WebSocket 是"假流式"** | 一次性生成后切 12 字 chunk 推送,无真正 token streaming | 改用 OpenAI stream=True |
| **`MergeDataset` 没用到** | 跨域评估场景缺失 | 沿用 XRV 的 MergeDataset 实现 |
| **knowledge 重建索引每次写都重建** | 数据量大时是 O(N²) | 增量更新 |
| **影像分析无 GPU 内存监控** | 大 batch 可能 OOM | 加 `torch.cuda.empty_cache()` 周期调用 |
| **OCR 文件无清理策略** | `ocr_uploads/` 永久增长 | 加 cron 或启动时清理 >30 天的 |
| **OpenAI SDK 锁到 1.x** | 没有用 Responses API 等新能力 | 升级到 2.x |
| **没有 rate limiting** | 单 IP 可刷爆 LLM 配额 | 加 slowapi |
| **WS 没有 reconnection backoff** | 网络抖动掉线 | 前端加指数退避 |
| **医生标注没触发模型重训** | 数据闭环断的 | 写个 `retrain.py` 消费 `doctor_annotation` |
| **vision OCR 的 timeout 180s 太长** | 用户体验差 | 改 async + SSE + 进度反馈 |
| **影像分析的 patient_id 没有外键** | 数据完整性差 | 加 FK to users(id) |

---

## 7. 部署与运行

### 7.1 本地开发

```bash
./scripts/start.sh
# 自动:venv + pip install + init_kb + 后端 :8000 + 前端 :5173
```

### 7.2 Docker Compose

```yaml
services:
  postgres: postgres:15-alpine     # 可选,默认 SQLite
  redis:    redis:7-alpine          # 可选
  backend:  FastAPI,挂载 knowledge_base/,init_kb 启动
  frontend: nginx + Vite dist
```

### 7.3 三种 LLM 模式

| 配置 | 用途 | 资源 |
|---|---|---|
| `mock` | 演示 / CI | 零 |
| `ollama` | 本地开发 | 7-30GB GPU/CPU |
| `openai` | 生产 | API 配额 |

### 7.4 关键环境变量

```bash
LLM_PROVIDER=mock|ollama|openai
OPENAI_BASE_URL=http://localhost:11434/v1   # ollama 自动填默认
OPENAI_MODEL=qwen-plus                     # 推荐非思考型 MoE
EMBEDDING_PROVIDER=mock|local|openai
OCR_ENGINE=auto|vision|tesseract|mock
OCR_VISION_MODEL=llama3.2-vision          # 留空跟随 OPENAI_MODEL
DATABASE_URL=sqlite+aiosqlite:///./data/medical.db
```

---

## 8. 开发者上手路径(推荐顺序)

1. **先跑 mock**:`./scripts/start.sh`,LLM_PROVIDER=mock 体验前端 + 后端全链路
2. **接 Ollama**:装 qwen-plus / glm-4-flash 这类**非思考型**模型,跑通问诊 + 结构化分析
3. **启用影像分析**:首次启动自动下载 `densenet121-res224-chex` 权重(~100MB)+ PSPNet(~250MB)
4. **加知识**:在 `knowledge_base/diseases/` 丢 MD,跑 `python scripts/init_kb.py` 重建索引
5. **试 OCR**:上传一张处方或化验单照片,看结构化效果
6. **管理后台**:用 admin/admin123 登录 `/admin`,体验 8 个模块
7. **接入真 LLM**:配置 OPENAI_API_KEY 切换到云端

---

## 9. 一句话评价

**架构合理、实战性强、不追求花哨**:
- 没有用 LangChain / LlamaIndex 等重型框架,自己写的 RAG + Agent + LLM 抽象,层数可控
- LLM/Embedding/OCR 三层各三档 provider,适配开发到生产的完整链路
- 思考型模型的适配是真的踩过坑的(不是抄 README)
- 影像分析接入 torchxrayvision 做到了"开箱即用",Grad-CAM + PSPNet 限制是亮点
- 唯一明显的妥协是 WebSocket 假流式 + Mock Embedding,但在演示场景下够用

这是一个**可以拿去给医院演示原型**的项目,不是又一个玩具 demo。

---

**分析基于 main 分支最新代码(后端 ~4700 行 + 前端 ~5100 行,统计剔除 venv/__pycache__/dist/node_modules)**