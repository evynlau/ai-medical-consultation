"""Medical Agent - 医疗问诊智能体(LangGraph 重构版)

对外保持原有方法签名:
    - analyze_symptoms(symptoms, user_context) -> Dict
    - chat(user_message, conversation_history, user_context) -> Dict
    - triage(symptoms) -> Dict
    - detect_emergency(text) -> bool
    - _parse_json_response(raw) -> Dict  (兼容旧调用)
    - _clean_reply(text) -> str          (兼容旧调用)

内部实现改为 LangGraph StateGraph 编排(见 app/agents/graph.py)。
API 路由 / WebSocket / 既有测试 都不需要改动。
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from app.agents.graph import get_analyze_graph, get_chat_graph, get_triage_graph
from app.agents.langchain_llm import detect_emergency, parse_json_response
from app.services.llm_service import LLMService
from app.utils.logger import logger


class MedicalAgent:
    """医疗问诊智能体(LangGraph 驱动)"""

    def __init__(self):
        # 三个图各取一次,后续 invoke() 复用
        self._chat_graph = get_chat_graph()
        self._analyze_graph = get_analyze_graph()
        self._triage_graph = get_triage_graph()

    # ====================== 公共方法(对外契约) ======================

    def detect_emergency(self, text: str) -> bool:
        return detect_emergency(text)

    async def analyze_symptoms(
        self,
        symptoms: str,
        user_context: Optional[Dict] = None,
        image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """结构化症状分析:返回 {reply, urgency_level, ..., reference_sources}

        image_path: 配套图片路径(可选),Agent 会自动调 OCR 或影像工具
        """
        state = {
            "input_user_message": symptoms,
            "input_user_context": user_context,
            "input_image_path": image_path,
        }
        out = await self._invoke_async(self._analyze_graph, state)
        # 最后一个节点 parse_and_attach 已把 payload 写到 state['result']
        return out.get("result", {})

    async def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        user_context: Optional[Dict] = None,
        image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """多轮对话模式:返回 {reply, is_emergency, urgency_level, source_knowledge[]}

        image_path: 配套图片路径(可选),Agent 会自动调 OCR 或影像工具
        多步问诊:LLM 输出若含追问,graph 会自动循环一轮(最多 2 次)
        """
        state = {
            "input_user_message": user_message,
            "input_conversation_history": conversation_history or [],
            "input_user_context": user_context,
            "input_image_path": image_path,
            "followup_round": 0,
        }
        out = await self._invoke_async(self._chat_graph, state)

        is_emergency = out.get("is_emergency", False)
        rag_results = out.get("rag_results") or []
        tool_results = out.get("tool_results") or []
        return {
            "reply": out.get("llm_raw", ""),
            "is_emergency": is_emergency,
            "urgency_level": 4 if is_emergency else 2,
            "source_knowledge": [
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "category": r.get("category"),
                    "content_preview": (r.get("content", "") or "")[:200],
                    "relevance": round(r.get("score", 0), 3),
                }
                for r in rag_results[:3]
            ],
            "tool_results": tool_results,
            "followup_rounds": out.get("followup_round", 0),
        }

    async def triage(
        self,
        symptoms: str,
        image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """快速分诊:返回 {department, urgency_level, urgency_label, reason, reference_sources}

        image_path: 配套图片路径(可选)
        """
        state = {
            "input_user_message": symptoms,
            "input_image_path": image_path,
        }
        out = await self._invoke_async(self._triage_graph, state)
        return out.get("result", {})

    # ====================== 兼容旧 API ======================

    def _clean_reply(self, text: str) -> str:
        """委托给 LLM 服务层统一清洗(保证所有出口行为一致)"""
        return LLMService._clean_reply(text)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """兼容旧 API;实际解析走 langchain_llm.parse_json_response"""
        return parse_json_response(raw)

    # ====================== 内部 ======================

    @staticmethod
    async def _invoke_async(graph, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph 同步 invoke 包装为 async(避免阻塞事件循环)"""
        def _call():
            return graph.invoke(state)

        return await asyncio.to_thread(_call)


# 单例
_agent: MedicalAgent | None = None


def get_medical_agent() -> MedicalAgent:
    global _agent
    if _agent is None:
        _agent = MedicalAgent()
    return _agent
