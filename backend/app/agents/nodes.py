"""LangGraph 节点

每个节点是一个 pure-ish 函数:输入 SymptomState,返回部分字段更新。
这种"小颗粒度节点 + 条件边"的拆分,对应了 LangGraph 相比裸函数链的
两个核心收益:
    1. 中间状态可被 LangSmith / .astream_log() 观测
    2. 可加条件边(如 emergency → 强制走紧急模板)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.langchain_llm import (
    detect_emergency,
    parse_json_response,
)
from app.agents.state import SymptomState
from app.agents.tools import (
    ALL_TOOLS,
    IMAGING_TOOL,
    OCR_TOOL,
    decide_tools_for_state,
)
from app.services.rag_service import get_rag_service
from app.services.llm_service import LLMService
from app.core.config import settings
from app.utils.logger import logger


# 追问启发式:LLM 输出的 reply 中含这些词,判定"在反问"→ 走 followup_round
_FOLLOWUP_HINT = re.compile(
    r"(\?|？|请问|多久|多少|有无|有没有|是否|能不能|请告诉|麻烦说|描述一下|"
    r"持续.{0,4}(?:多久|多长时间)|伴随|其他.{0,2}(?:症状|不舒服)|"
    r"用药|过敏|既往|慢病|什么时候开始)",
    re.IGNORECASE,
)

MAX_FOLLOWUP_ROUND = 2  # 最多连续追问 2 轮(避免死循环)


# ====================== 工具节点 ======================

def invoke_tools_node(state: SymptomState) -> Dict[str, Any]:
    """根据 image_path 调相应工具

    - 真 LLM 模式(非 mock):走 bind_tools() + ToolNode(在 graph 里另设)
      本节点处理降级路径 / mock 路径
    - mock 模式:用 decide_tools_for_state() 选工具并直接调
    """
    image_path = state.get("input_image_path")
    if not image_path:
        return {"tool_results": [], "tool_text": ""}

    is_mock = (settings.LLM_PROVIDER or "").lower().strip() == "mock"
    results: list = []
    if is_mock:
        # mock 模式:启发式选工具
        tools = decide_tools_for_state(image_path)
        logger.info(f"[ToolNode-mock] image={image_path}, tools={[t.name for t in tools]}")
        for tool in tools:
            try:
                if tool.name == OCR_TOOL.name:
                    out = tool.invoke({"file_path": image_path, "image_type_hint": "auto"})
                else:
                    out = tool.invoke({"file_path": image_path, "generate_gradcam": False})
            except Exception as e:
                logger.warning(f"[ToolNode-mock] {tool.name} 失败: {e}")
                out = {"success": False, "error": str(e)}
            results.append({"name": tool.name, "output": out})
    else:
        # 真 LLM 模式:工具调用由 ToolNode 节点(本图外)在 llm_invoke 前后做
        # 此节点仅在 llm_invoke 跳过(模拟)时提供降级通道
        # 实际生产中,graph 拓扑应包含 ToolNode;此处保持简单
        logger.info(f"[ToolNode-pass] image={image_path} (真 LLM ToolNode 接管)")
        return {"tool_results": [], "tool_text": ""}

    # 把结果拼成 prompt 片段
    chunks = ["\n\n【图片识别结果】\n"]
    for r in results:
        name = r.get("name", "?")
        out = r.get("output", {}) or {}
        if not out.get("success"):
            chunks.append(f"- {name}: 失败({out.get('error', '未知错误')})\n")
            continue
        if name == OCR_TOOL.name:
            text = out.get("raw_text", "")[:600]
            chunks.append(f"- OCR 识别(引擎:{out.get('engine','?')}):\n  {text}\n")
        elif name == IMAGING_TOOL.name:
            diagnosis = out.get("diagnosis_cn") or out.get("diagnosis") or "N/A"
            confidence = out.get("confidence")
            positive_count = out.get("positive_count", 0)
            pathologies = out.get("pathologies", []) or []
            # 提取 Pneumonia 概率 + 阳性标签
            pneumonia_prob = None
            for p in pathologies:
                if (p.get("pathology") or "").lower() == "pneumonia":
                    pneumonia_prob = p.get("probability")
                    break
            positives = [p for p in pathologies if p.get("positive")]
            top_str = ", ".join(
                f"{p.get('label_cn') or p.get('pathology')}({p.get('probability', 0):.2f})"
                for p in positives[:5]
            ) if positives else "无阳性"
            chunks.append(
                f"- 胸片诊断:{diagnosis};置信度={confidence};阳性项数={positive_count}\n"
                f"  阳性标签:{top_str}\n"
                + (f"  肺炎概率={pneumonia_prob:.3f}\n" if pneumonia_prob is not None else "")
            )
    return {"tool_results": results, "tool_text": "".join(chunks)}


# ====================== 追问决策 ======================

def decide_continue_node(state: SymptomState) -> Dict[str, Any]:
    """启发式:reply 中含问号/请问/多久等 → need_followup=True

    不改 LLM 输出格式(避免动 mock 模板)。
    配合 MAX_FOLLOWUP_ROUND 限流,避免死循环。
    """
    raw = state.get("llm_raw", "") or ""
    round_n = state.get("followup_round", 0)
    if round_n >= MAX_FOLLOWUP_ROUND:
        return {"need_followup": False}
    need = bool(_FOLLOWUP_HINT.search(raw))
    return {"need_followup": need}


def incr_followup_node(state: SymptomState) -> Dict[str, Any]:
    """走过一轮追问后 +1,供下次 should_continue 决策"""
    return {"followup_round": state.get("followup_round", 0) + 1}


# ====================== 系统提示(原 medical_agent._build_system_prompt) ======================

def build_system_prompt(user_context=None) -> str:
    base = """你是一位专业、经验丰富的 AI 医学助手,负责在用户描述症状时提供辅助分析。

【你的职责】
1. 症状分析:通过多轮对话收集信息,辅助识别可能的病因
2. 智能分诊:判断紧急程度,推荐就诊科室
3. 健康建议:给出生活护理、检查方向的建议
4. 健康教育:解释疾病知识

【重要原则】
- 你的建议仅供参考,不能替代医生的面诊和检查
- 遇到紧急症状(胸痛、呼吸困难、大出血、意识障碍、剧烈头痛等),必须立即提示就医
- 不确定时,建议用户线下就诊
- 保持专业、耐心、温暖的语气
- 不开具体处方药,只建议方向

【回复风格】
- 中文,简洁明了
- 结构化(分点或小标题)
- 关键建议加粗
- 末尾附免责声明"""

    if user_context:
        ctx = []
        if user_context.get("age"):
            ctx.append(f"年龄:{user_context['age']}")
        if user_context.get("gender"):
            ctx.append(f"性别:{user_context['gender']}")
        if user_context.get("allergies"):
            ctx.append(f"过敏史:{user_context['allergies']}")
        if user_context.get("chronic_diseases"):
            ctx.append(f"慢性病:{user_context['chronic_diseases']}")
        if ctx:
            base += "\n\n【患者基本信息】\n" + "\n".join(ctx)

    return base


# ====================== 节点 ======================

def detect_emergency_node(state: SymptomState) -> Dict[str, Any]:
    """紧急识别(无外部依赖,纯正则)"""
    msg = state.get("input_user_message", "")
    is_emergency = detect_emergency(msg)
    return {"is_emergency": is_emergency}


def retrieve_knowledge_node(state: SymptomState) -> Dict[str, Any]:
    """RAG 检索(失败时降级,不让节点抛错中断图)"""
    msg = state.get("input_user_message", "")
    try:
        rag = get_rag_service()
        results = rag.hybrid_search(query=msg, top_k=5)
        return {
            "rag_results": results or [],
            "rag_failed": False,
        }
    except Exception as e:
        logger.warning(f"RAG 检索失败,降级到无知识库模式: {e}")
        return {
            "rag_results": [],
            "rag_failed": True,
        }


def format_knowledge_node(state: SymptomState) -> Dict[str, Any]:
    """把 rag_results 拼成可注入 prompt 的字符串"""
    results = state.get("rag_results") or []
    if not results:
        return {"knowledge_text": ""}
    chunks = ["\n\n【相关医学知识参考】\n"]
    for i, doc in enumerate(results, 1):
        content = (doc.get("content") or "")[:500]
        chunks.append(
            f"\n{i}. 《{doc.get('title', '医学知识')}》({doc.get('category', '')})\n{content}\n"
        )
    return {"knowledge_text": "".join(chunks)}


def build_messages_node(state: SymptomState) -> Dict[str, Any]:
    """组装给 LLM 的消息列表(对应原 chat() 流程)"""
    user_msg = state.get("input_user_message", "")
    history = state.get("input_conversation_history") or []
    user_context = state.get("input_user_context")
    is_emergency = state.get("is_emergency", False)
    knowledge_text = state.get("knowledge_text", "")
    tool_text = state.get("tool_text", "")

    messages: list = [{"role": "system", "content": build_system_prompt(user_context)}]

    if history:
        for m in history[-10:]:
            role = m.get("role")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    if is_emergency:
        prefix = "⚠️ 检测到可能的紧急症状,请先提示用户立即就医,然后再给建议。\n\n"
    else:
        prefix = ""

    current = f"{prefix}参考知识:{knowledge_text}{tool_text}\n\n患者说:{user_msg}"
    messages.append({"role": "user", "content": current})

    return {"messages": messages}


# ====================== LangChain Message 转换 ======================

def _dict_to_lc_messages(messages: list) -> list:
    out = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "user":
            out.append(HumanMessage(content=content))
        else:
            from langchain_core.messages import AIMessage
            out.append(AIMessage(content=content))
    return out
