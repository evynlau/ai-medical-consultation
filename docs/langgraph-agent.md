# LangGraph Agent 重构设计文档

> 版本:2026-06-15
> 范围:`app/agents/` 下三个 LangGraph StateGraph + 一层 langchain ChatModel 适配

## 1. 重构目标

把原有的"自研 `MedicalAgent` 类"重构为 **LangGraph StateGraph**,获得:

1. **可观测性**:`graph.stream()` / `graph.astream_log()` 让中间状态可视化,方便调试
2. **节点复用**:`detect_emergency` / `retrieve_knowledge` / `format_knowledge` 在三个图中共享
3. **条件边扩展位**:未来可加 `if is_emergency: skip_knowledge` 这类分支
4. **LangChain 生态入场券**:未来接 LangSmith、Tool Calling、Memory Store 不需要再换框架

## 2. 不动的部分(刻意保持稳定)

| 模块 | 状态 | 原因 |
|---|---|---|
| `app/services/llm_service.py` | **不动** | OCR / imaging / WebSocket 三处外部消费者直接依赖 `_clean_reply` / `build_thinking_disable_kwargs` 等模块级函数 |
| `app/services/rag_service.py` | **不动** | FAISS 索引持久化格式已稳定,迁移到 langchain-community FAISS 收益不大 |
| 对外 HTTP/WS API | **不动** | `consult.py` / `agent.py` / `ws/chat.py` 继续 `from app.agents.medical_agent import get_medical_agent`,签名不变 |
| 思考型模型清洗 | **委托给 LLMService** | 那一大段 `_clean_reply` / `_extract_final_answer` 里有几十条经验性正则,重写风险大 |

## 3. 架构

```
┌──────────────────────────────────────────────────────────────┐
│ consult.py / agent.py / ws/chat.py                           │
│      ↓ (调用未变)                                            │
│ get_medical_agent() → MedicalAgent(类签名未变)                │
│      ↓                                                       │
│   ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐  │
│   │  chat_graph     │  │  analyze_graph   │  │ triage_gr. │  │
│   │  (多轮对话)     │  │  (结构化分析)    │  │ (轻量分诊) │  │
│   └────────┬────────┘  └─────────┬────────┘  └─────┬──────┘  │
│            └──────────────┬──────┴─────────────────┘         │
│                           ▼                                  │
│              app/agents/nodes.py (共享节点)                  │
│                           │                                  │
│                           ▼                                  │
│   ┌────────────────────────────────────────────────────┐     │
│   │ app/agents/langchain_llm.py                        │     │
│   │  - MedicalMockChatModel (FakeListChatModel)        │     │
│   │  - MedicalOpenAIChatModel (init_chat_model)        │     │
│   │  - 委托 LLMService._clean_reply 做思考型清洗       │     │
│   └────────────────────────────────────────────────────┘     │
│                           │                                  │
│                           ▼                                  │
│              app/services/llm_service.py (原样)             │
└──────────────────────────────────────────────────────────────┘
```

## 4. 三个图

### 4.1 chat_graph(多轮对话,带 should_continue 循环)

```
START
  → detect_emergency        # 正则识别紧急症状
  → retrieve_knowledge      # FAISS 混合检索
  → invoke_tools            # 有 image_path 才调(OCR/影像),无则透传
  → format_knowledge        # 把 hits 拼成 prompt 片段
  → build_messages          # 拼装 system + history + tool_text + user
  → llm_invoke(t=0.5)       # 调用 ChatModel
  → decide_continue ──[need_followup=True, followup_round<2]──→ incr_followup → build_messages(循环)
                       └─[need_followup=False 或 round>=2]──→ END
```

`MAX_FOLLOWUP_ROUND=2`:防止死循环,真实场景下真 LLM 给出"完整答案"时
`need_followup=False` 一次结束;mock 模板永远追问时会卡到 2 轮兜底退出。

**decide_continue 启发式**(不动 LLM 输出格式,避免动 mock 模板):
读 `llm_raw` 字符串,匹配下列任一即 `need_followup=True`:
- 含 `?` 或 `？`
- 含 `请问` / `多久` / `多少` / `有无` / `有没有` / `是否` / `能不能` / `请告诉` / `麻烦说` / `描述一下` / `伴随` / `用药` / `过敏` / `既往` / `慢病` / `什么时候开始`
- `持续.{0,4}(?:多久|多长时间)` / `其他.{0,2}(?:症状|不舒服)`

### 4.2 analyze_graph(结构化症状分析)

在 chat_graph 基础上,**无 should_continue 循环**(结构化分析一次到位);
`build_messages` 换成结构化 JSON 模板,新增 `parse_and_attach` 节点做
JSON 解析 + 紧急结果合并 + 来源附加。

支持 `image_path`:`invoke_tools` 节点会调对应工具。

### 4.3 triage_graph(智能分诊)

在 analyze_graph 基础上,prompt 更精简(只输出 department/urgency/reason),
`parse_and_attach` 只附加 triage 形态的来源。

支持 `image_path`。

## 4.5 工具节点(invoke_tools)

见 `app/agents/nodes.py:invoke_tools_node`,根据 `image_path` 调相应工具。

**降级策略**:
- `LLM_PROVIDER=mock`:走 `decide_tools_for_state()`,按文件名启发式
  选 OCR 或影像工具(关键词含 `prescription`/`处方`/`report`/`报告`/
  `化验`/`lab` → OCR;默认 → 影像)
- `LLM_PROVIDER=openai/ollama`:生产环境应接入 `langgraph.prebuilt.ToolNode`
  + `ChatModel.bind_tools()`,由 LLM 自主决策。本框架留有扩展位
  (`MedicalOpenAIChatModel` 可改 `.bind_tools(ALL_TOOLS)`),但 mock 路径
  直接决策以保持 LLM 无关

**工具列表**(见 `app/agents/tools.py`):
- `ocr_recognize(file_path, image_type_hint)`:包装 `OCRService.recognize`
- `chest_xray_analyze(file_path, generate_gradcam)`:包装
  `XRVAnalysisService.predict_from_bytes{,_with_gradcam}`

## 5. ChatModel 适配

`langchain_llm.py` 提供两个 `BaseChatModel` 子类:

### MedicalMockChatModel

`LLM_PROVIDER=mock` 时启用。**把 `llm_service._mock_chat` 包成 langchain 接口**,
内部把 langchain `BaseMessage` 还原为 `[{role, content}]` dict 后透传给原 mock 模板,
保证 mock 行为与重构前**逐字符一致**。

### MedicalOpenAIChatModel

`LLM_PROVIDER=openai/ollama` 时启用。内部用 `langchain_openai.ChatOpenAI`:

- Ollama 自动注入 `model_kwargs={"think": False}`(跳过 0.6+ 思考)
- MiniMax 注入 `extra_body={"thinking": {"type": "disabled"}}`
- 响应走 `LLMService._clean_reply` 做全局清洗
- 调用失败 / 响应为空时,降级到 mock(与原 `llm_service.chat` 一致)

## 6. 状态字段约定

见 `app/agents/state.py:SymptomState`,命名分三组:

- `input_*`:入口注入,节点只读
- 中间字段:节点读写
- `result`:最后一个节点负责组装

## 7. 使用方式

### 7.1 代码内调用(无变化 + image_path 可选)

```python
from app.agents.medical_agent import get_medical_agent

agent = get_medical_agent()

# 纯文本(向后兼容)
result = await agent.analyze_symptoms("我最近头痛三天")

# 配套图片
result = await agent.analyze_symptoms(
    "我胸痛,刚拍胸片",
    image_path="/data/uploads/xray_20260615.png",
)

# 多轮对话(可能触发 1-2 轮追问)
result = await agent.chat("我感冒了")
print(result["followup_rounds"])  # 0, 1, or 2
print(result["tool_results"])      # 工具调用结果
```

### 7.2 WebSocket 加 image 字段

```json
{
  "action": "chat",
  "data": {
    "consultation_id": 42,
    "content": "看看这张化验单",
    "image_path": "/data/uploads/lab_20260615.png"
  }
}
```

`image_path` 字段为可选;不传则行为与重构前一致。

### 7.2 单独调用图

```python
from app.agents.graph import get_chat_graph

graph = get_chat_graph()
# 同步
out = graph.invoke({"input_user_message": "我头痛"})
# 流式(可选,用于前端打字机效果)
for chunk in graph.stream({"input_user_message": "我头痛"}, stream_mode="updates"):
    print(chunk)
```

### 7.3 渲染图为 Mermaid

```bash
cd backend
venv/bin/python ../scripts/render_graph.py ../docs/graphs
```

会输出:
- `docs/graphs/chat_graph.mmd`
- `docs/graphs/analyze_graph.mmd`
- `docs/graphs/triage_graph.mmd`

把 `.mmd` 内容贴到 https://mermaid.live 即可预览。

## 8. 验证清单(交付时核对)

- [x] `requirements.txt` 加入 `langchain` / `langchain-openai` / `langgraph` / `langchain-community`
- [x] `app/agents/state.py` 存在且导出 `SymptomState`
- [x] `app/agents/nodes.py` 至少包含 4 个节点函数 (+ `invoke_tools_node` / `decide_continue_node` / `incr_followup_node`)
- [x] `app/agents/langchain_llm.py` 提供 `build_chat_model()` 工厂
- [x] `app/agents/graph.py` 提供 `get_chat_graph()` / `get_analyze_graph()` / `get_triage_graph()`
- [x] `app/agents/tools.py` 提供 `OCR_TOOL` / `IMAGING_TOOL` / `ALL_TOOLS`
- [x] `chat_graph` 加 `should_continue` 条件边(`decide_continue` → `incr_followup` → `build_messages` 循环,`MAX_FOLLOWUP_ROUND=2`)
- [x] `MedicalAgent` 类保留 `analyze_symptoms` / `chat` / `triage` / `detect_emergency` 方法签名(+ `image_path` 可选参数)
- [x] `MedicalAgent.chat()` 返回加 `tool_results` / `followup_rounds` 字段
- [x] `ws/chat.py` 接收 `image_path` 可选字段
- [x] `app/services/llm_service.py` 文件未修改
- [x] `scripts/render_graph.py` 可执行并产出 mermaid(图中能看见条件边 + 循环边)
- [x] 服务能启动 + `/health` 返回 200 + WS 可连接
- [x] mock 端到端:无图不调工具 / 有图按文件名分流 / 紧急路径仍生效

## 9. 后续可选优化(本次未做)

- **真 LLM 工具调用**:把 `MedicalOpenAIChatModel` 改造为 `bind_tools(ALL_TOOLS)` + 接入 `langgraph.prebuilt.ToolNode`,让 LLM 自主决策调哪个工具。mock 路径不变(用 `decide_tools_for_state` 兜底)。
- 接入 LangSmith(`LANGCHAIN_TRACING_V2=true` 即可,无需改代码)
- 把 `_clean_reply` 改写为 `BaseOutputParser`,但本次刻意保留 `LLMService` 形态以减小风险
- Tool Calling:加 `tool_node` 接入医学影像 / OCR 工具(本次已部分完成:`tools.py` 提供包装,graph 接入位置已留 `invoke_tools_node`)
