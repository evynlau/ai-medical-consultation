"""LangGraph StateGraph 装配

图结构(对应原 medical_agent 多轮对话 chat() 流程):

    START
      ↓
    detect_emergency_node
      ↓
    retrieve_knowledge_node
      ↓
    format_knowledge_node
      ↓
    build_messages_node
      ↓
    llm_invoke_node
      ↓
     END

analyze_symptoms / triage 走专用子图(见 build_analyze_graph / build_triage_graph)
"""
from __future__ import annotations

from typing import Any, Dict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from app.agents.langchain_llm import build_chat_model, parse_json_response
from app.agents.nodes import (
    _dict_to_lc_messages,
    build_messages_node,
    build_system_prompt,
    decide_continue_node,
    detect_emergency_node,
    format_knowledge_node,
    incr_followup_node,
    invoke_tools_node,
    retrieve_knowledge_node,
)
from app.agents.state import SymptomState
from app.utils.logger import logger


# ====================== 公共 LLM 节点 ======================

def make_llm_invoke_node(default_temperature: float = 0.5, default_max_tokens: int = 1200):
    """工厂:生成一个调用 LLM 的节点
    - 闭包捕获 chat_model,避免每次都重新构造(单例)
    - 节点读取 state['messages'] 转为 langchain message 后 invoke
    """
    chat_model = build_chat_model()
    temperature = default_temperature
    max_tokens = default_max_tokens

    def _node(state: SymptomState) -> Dict[str, Any]:
        lc_messages = _dict_to_lc_messages(state.get("messages") or [])
        resp = chat_model.invoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.content if hasattr(resp, "content") else str(resp)
        return {"llm_raw": content}

    return _node


# ====================== 多轮对话图 ======================

def build_chat_graph():
    """多轮对话 chat() 用的图

    拓扑(should_continue 条件边):
        START
          → detect_emergency
          → retrieve_knowledge
          → invoke_tools          # 有 image_path 才调,无则透传
          → format_knowledge
          → build_messages
          → llm_invoke
          → decide_continue ──need_followup=True──→ incr_followup → build_messages(循环)
                                  └─need_followup=False──→ END
    """
    graph = StateGraph(SymptomState)
    graph.add_node("detect_emergency", detect_emergency_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge_node)
    graph.add_node("invoke_tools", invoke_tools_node)
    graph.add_node("format_knowledge", format_knowledge_node)
    graph.add_node("build_messages", build_messages_node)
    graph.add_node("llm_invoke", make_llm_invoke_node(default_temperature=0.5, default_max_tokens=1200))
    graph.add_node("decide_continue", decide_continue_node)
    graph.add_node("incr_followup", incr_followup_node)

    graph.add_edge(START, "detect_emergency")
    graph.add_edge("detect_emergency", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "invoke_tools")
    graph.add_edge("invoke_tools", "format_knowledge")
    graph.add_edge("format_knowledge", "build_messages")
    graph.add_edge("build_messages", "llm_invoke")
    graph.add_edge("llm_invoke", "decide_continue")

    # 条件边:追问 or 结束
    graph.add_conditional_edges(
        "decide_continue",
        lambda s: "followup" if s.get("need_followup") else "end",
        {
            "followup": "incr_followup",
            "end": END,
        },
    )
    graph.add_edge("incr_followup", "build_messages")  # 重新拼消息 → 再调 LLM

    return graph.compile()


# ====================== analyze_symptoms 专用节点 ======================

def build_analyze_messages_node(state: SymptomState) -> Dict[str, Any]:
    symptoms = state.get("input_user_message", "")
    user_context = state.get("input_user_context")
    knowledge_text = state.get("knowledge_text", "")

    analysis_prompt = f"""请分析以下患者症状,并以 JSON 格式返回结构化结果。

【患者症状】
{symptoms}
{knowledge_text}

【输出要求 - 严格 JSON】
{{
  "reply": "对患者友好的回复文字(2-4 段,温暖专业)",
  "urgency_level": 1-4 的整数(1=无需就医,2=择期就医,3=尽快就医,4=立即急诊),
  "needs_urgent_care": true/false,
  "possible_causes": ["可能原因1", "可能原因2", "可能原因3"],
  "suggested_examinations": ["建议检查1", "建议检查2"],
  "department": "推荐就诊科室",
  "self_care_tips": ["护理建议1", "护理建议2", "护理建议3"]
}}

【严禁事项】
- 严禁在 reply 字段包含思考/规划/自检文本(如 "Check against Constraints"、"Draft JSON"、"Map to JSON Schema"、"Analyze User Input" 等)
- 严禁在 JSON 外加任何解释文字
- reply 字段必须是**直接给患者看的、温暖专业的医学分析**
- 其他字段必须是干净的列表/数值/布尔,不要带 markdown 标记"""

    messages = [
        {"role": "system", "content": build_system_prompt(user_context)},
        {"role": "user", "content": analysis_prompt},
    ]
    return {"messages": messages}


def parse_analyze_node(state: SymptomState) -> Dict[str, Any]:
    """解析 LLM 输出的 JSON + 合并紧急识别结果 + 附加 RAG 来源"""
    from app.services.llm_service import LLMService

    raw = state.get("llm_raw", "")
    result = parse_json_response(raw)
    if result.get("reply"):
        result["reply"] = LLMService._clean_reply(result["reply"])

    is_emergency = state.get("is_emergency", False)
    if is_emergency and not result.get("needs_urgent_care"):
        result["needs_urgent_care"] = True
        result["urgency_level"] = max(result.get("urgency_level", 3), 4)

    rag_results = state.get("rag_results") or []
    result["reference_sources"] = [
        {
            "id": r.get("id"),
            "title": r.get("title"),
            "category": r.get("category"),
            "relevance": round(r.get("score", 0), 3),
        }
        for r in rag_results[:3]
    ]
    return {"result": result, "parsed": result}


def build_analyze_graph():
    """结构化症状分析 analyze_symptoms() 用的图"""
    graph = StateGraph(SymptomState)
    graph.add_node("detect_emergency", detect_emergency_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge_node)
    graph.add_node("format_knowledge", format_knowledge_node)
    graph.add_node("build_messages", build_analyze_messages_node)
    graph.add_node(
        "llm_invoke",
        make_llm_invoke_node(default_temperature=0.3, default_max_tokens=1500),
    )
    graph.add_node("parse_and_attach", parse_analyze_node)

    graph.add_edge(START, "detect_emergency")
    graph.add_edge("detect_emergency", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "format_knowledge")
    graph.add_edge("format_knowledge", "build_messages")
    graph.add_edge("build_messages", "llm_invoke")
    graph.add_edge("llm_invoke", "parse_and_attach")
    graph.add_edge("parse_and_attach", END)
    return graph.compile()


# ====================== triage 专用节点 ======================

def build_triage_messages_node(state: SymptomState) -> Dict[str, Any]:
    symptoms = state.get("input_user_message", "")
    knowledge_text = state.get("knowledge_text", "")

    # 复用 build_messages_node 的逻辑不可行(模板不同),这里直接组装
    if knowledge_text:
        knowledge_text_full = "\n参考知识:\n" + "\n".join(
            f"- {d.get('title', '')}: {d.get('content', '')[:200]}"
            for d in (state.get("rag_results") or [])
        ) + "\n"
    else:
        knowledge_text_full = ""

    prompt = f"""根据患者症状,快速给出分诊建议。

症状:{symptoms}
{knowledge_text_full}

请用 JSON 输出:
{{
  "department": "推荐科室",
  "urgency_level": 1-4,
  "urgency_label": "文字说明(立即急诊/尽快就医/择期就医/无需就医)",
  "reason": "推荐理由(1-2 句)"
}}"""

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": prompt},
    ]
    return {"messages": messages}


def parse_triage_node(state: SymptomState) -> Dict[str, Any]:
    raw = state.get("llm_raw", "")
    result = parse_json_response(raw)
    is_emergency = state.get("is_emergency", False)
    if is_emergency and result.get("urgency_level", 0) < 4:
        result["urgency_level"] = 4
        result["urgency_label"] = "立即急诊"
    rag_results = state.get("rag_results") or []
    result["reference_sources"] = [
        {"title": r.get("title"), "relevance": round(r.get("score", 0), 3)}
        for r in rag_results[:3]
    ]
    return {"result": result, "parsed": result}


def build_triage_graph():
    """智能分诊 triage() 用的图"""
    graph = StateGraph(SymptomState)
    graph.add_node("detect_emergency", detect_emergency_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge_node)
    graph.add_node("format_knowledge", format_knowledge_node)
    graph.add_node("build_messages", build_triage_messages_node)
    graph.add_node(
        "llm_invoke",
        make_llm_invoke_node(default_temperature=0.2, default_max_tokens=600),
    )
    graph.add_node("parse_and_attach", parse_triage_node)

    graph.add_edge(START, "detect_emergency")
    graph.add_edge("detect_emergency", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "format_knowledge")
    graph.add_edge("format_knowledge", "build_messages")
    graph.add_edge("build_messages", "llm_invoke")
    graph.add_edge("llm_invoke", "parse_and_attach")
    graph.add_edge("parse_and_attach", END)
    return graph.compile()


# ====================== 单例 ======================

_chat_graph = None
_analyze_graph = None
_triage_graph = None


def get_chat_graph():
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = build_chat_graph()
    return _chat_graph


def get_analyze_graph():
    global _analyze_graph
    if _analyze_graph is None:
        _analyze_graph = build_analyze_graph()
    return _analyze_graph


def get_triage_graph():
    global _triage_graph
    if _triage_graph is None:
        _triage_graph = build_triage_graph()
    return _triage_graph
