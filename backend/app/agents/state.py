"""LangGraph 状态定义

MedicalAgent 重构为 StateGraph 后,所有节点读/写这一个状态对象。
字段尽量只增不改,以保持与既有 API 契约(consult.py / agent.py / ws/chat.py)
对返回结构的一致性。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class SymptomState(TypedDict, total=False):
    """问诊流程共享状态

    字段约定:
        - 入参字段(input_ 前缀):节点不可写,只在入口注入
        - 中间字段:节点可写
        - 出参字段:最后一个 generate_response 节点负责组装
    """
    # ----- 入参 -----
    input_user_message: str                # 用户这一轮的输入
    input_conversation_history: List[Dict]  # 多轮对话历史(由调用方传入)
    input_user_context: Optional[Dict]      # 患者基本信息
    input_image_path: Optional[str]         # 配套图片(可选;有则触发工具)

    # ----- 中间 -----
    is_emergency: bool                      # 紧急识别结果
    rag_results: List[Dict]                # 检索到的知识库片段
    rag_failed: bool                        # RAG 检索是否失败(用于降级)
    knowledge_text: str                     # 拼进 prompt 的知识摘要
    tool_results: List[Dict]                # 工具调用结果 [{name, output, success}, ...]
    tool_text: str                          # 工具结果拼成 prompt 片段
    messages: List[Dict]                    # 即将送给 LLM 的消息列表
    llm_raw: str                            # LLM 原始输出
    parsed: Dict                            # JSON 解析结果(analyze / triage 模式)
    followup_round: int                     # 已走的追问轮数(0..MAX_FOLLOWUP)
    need_followup: bool                     # 启发式判定:本轮是否需追问

    # ----- 出参 -----
    result: Dict[str, Any]                  # 最终给前端的 dict
