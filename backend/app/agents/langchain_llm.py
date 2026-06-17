"""LangChain ChatModel 适配层

设计目标:
    1. 让 MedicalAgent 节点完全使用 langchain 接口 (BaseChatModel)
    2. LLM_PROVIDER=mock 走 FakeListChatModel(队列耗尽则按 mock 模板兜底)
    3. LLM_PROVIDER=openai/ollama 走 init_chat_model(支持 ChatOpenAI)
    4. 思考型模型清洗逻辑委托给既有 LLMService._clean_reply(不重写)
    5. 透传 disable_thinking:Ollama 注入 think=False,MiniMax 注入 extra_body

不重写 llm_service.py 的原因:OCR / imaging / WebSocket 三处仍依赖
build_thinking_disable_kwargs / get_llm_service / _clean_reply,本模块只是
在 Agent 内部把"原生 messages + 清洗"包成 langchain 的 BaseChatModel 形态。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.core.config import settings
from app.services.llm_service import LLMService
from app.utils.logger import logger


# 复用原 LLMService 的思考型清洗 + 紧急识别,避免双份实现
# _mock_chat 是 instance method,需要 self;其他 _clean_reply / _extract_final_answer 是 staticmethod,可直接调
_mock_chat_fn = LLMService._mock_chat
_clean_reply_fn = LLMService._clean_reply
_extract_final_answer_fn = LLMService._extract_final_answer


def LLMService_instance() -> LLMService:
    """取一个 LLMService 实例(用于调用 _mock_chat)

    注意:不用单例,因为 LLMService 内部状态(AsyncOpenAI client)只对
    openai/ollama 路径有意义;mock 路径每次拿一个新实例更省事。
    """
    return LLMService()


# ====================== Mock ChatModel ======================

class MedicalMockChatModel(BaseChatModel):
    """LLM_PROVIDER=mock 时的 ChatModel 适配

    - 输入消息透传给原 LLMService._mock_chat
    - 行为与重构前完全一致(模板分支 / followup / 紧急分诊)
    """

    # 提示结构:不强制 temperature / max_tokens,模板忽略它们
    model_name: str = "mock-medical"

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "mock-medical"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 还原成 OpenAI 风格的 [{role, content}] 给 _mock_chat
        legacy_messages = [_to_legacy(m) for m in messages]
        # _mock_chat 是 instance method,需要 LLMService 实例
        content = _mock_chat_fn(LLMService_instance(), legacy_messages)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=content))]
        )


# ====================== OpenAI 兼容 ChatModel ======================

class MedicalOpenAIChatModel(BaseChatModel):
    """LLM_PROVIDER=openai/ollama 时的 ChatModel 适配

    - 透传 base_url / api_key / model 给 ChatOpenAI
    - 对 Ollama 注入 think=False,对 MiniMax 注入 extra_body(thinking disable)
    - 响应做 _clean_reply(委托给 LLMService)
    """

    model: str = ""
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.5
    max_tokens: int = 1500
    is_ollama: bool = False
    is_minimax: bool = False
    is_thinking_capable: bool = True

    # 内部 ChatOpenAI 引用(延迟构造)
    _inner: Any = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "openai-compatible"

    def _ensure_inner(self) -> None:
        if self._inner is not None:
            return
        from langchain_openai import ChatOpenAI

        kwargs: Dict[str, Any] = {
            "model": self.model or settings.OPENAI_MODEL,
            "api_key": self.api_key or settings.OPENAI_API_KEY or "ollama",
            "base_url": self.base_url or settings.OPENAI_BASE_URL,
            "timeout": float(settings.API_RESPONSE_TIMEOUT),
        }
        if self.is_ollama and self.is_thinking_capable:
            # Ollama 0.6+ 支持 think=False 跳过内部思考
            kwargs["model_kwargs"] = {"think": False}
        if self.is_minimax and self.is_thinking_capable:
            # MiniMax 通过 extra_body 注入 vendor-specific 参数
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        self._inner = ChatOpenAI(**kwargs)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._ensure_inner()

        # 取出本轮 temperature / max_tokens(允许节点覆盖)
        temperature = kwargs.pop("temperature", self.temperature)
        max_tokens = kwargs.pop("max_tokens", self.max_tokens)

        try:
            resp = self._inner.invoke(
                [_to_lc(m) for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f"[LangChainLLM] 调用失败: {type(e).__name__}: {e}")
            logger.error(
                "[LangChainLLM] 检查项: 1) Ollama 是否运行? "
                f"2) 模型 '{self.model or settings.OPENAI_MODEL}' 是否已下载? "
                f"3) base_url '{self.base_url or settings.OPENAI_BASE_URL}' 是否可达?"
            )
            # 失败降级到 mock(原 llm_service 行为)
            content = _mock_chat_fn(LLMService_instance(), [_to_legacy(m) for m in messages])
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

        # 提取 content 与 reasoning(兼容思考型模型)
        content = (getattr(resp, "content", "") or "").strip()
        reasoning = (
            getattr(resp, "additional_kwargs", {}).get("reasoning_content", "")
            or getattr(resp, "additional_kwargs", {}).get("reasoning", "")
        )
        if not content and reasoning:
            # content 为空才去 reasoning 找答案
            content = _extract_final_answer_fn(reasoning) or content
        if not content:
            # 都没内容,降级 mock
            logger.warning("[LangChainLLM] 响应为空,降级到 mock")
            content = _mock_chat_fn(LLMService_instance(), [_to_legacy(m) for m in messages])

        # 全局清洗(委托给 LLMService)
        content = _clean_reply_fn(content)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


# ====================== 工厂函数 ======================

_URGENT_KEYWORDS = [
    "胸痛", "剧烈胸痛", "压榨性胸痛", "心绞痛",
    "呼吸困难", "喘不过气", "窒息",
    "大出血", "大量出血", "呕血", "咯血",
    "昏迷", "意识不清", "突然晕倒", "昏厥",
    "剧烈头痛", "突发头痛", "爆炸样头痛",
    "偏瘫", "口角歪斜", "言语不清", "中风",
    "剧烈腹痛", "刀割样痛",
    "高热惊厥", "抽搐",
    "自杀", "自残",
    "车祸", "严重外伤", "高处坠落",
    "中毒", "误服",
]
_URGENT_REGEX = re.compile("|".join(_URGENT_KEYWORDS))


def detect_emergency(text: str) -> bool:
    """紧急症状关键词识别(与原 medical_agent.py 行为一致)"""
    return bool(_URGENT_REGEX.search(text or ""))


def detect_is_ollama(base_url: str = "") -> bool:
    url = (base_url or settings.OPENAI_BASE_URL or "").lower()
    return "11434" in url and "/v1" in url


def detect_is_minimax(base_url: str = "") -> bool:
    url = (base_url or settings.OPENAI_BASE_URL or "").lower()
    return "minimaxi" in url or "minimax" in url


def detect_is_thinking_capable(model_name: str = "", base_url: str = "") -> bool:
    if detect_is_ollama(base_url):
        model = (model_name or settings.OPENAI_MODEL or "").lower()
        non_thinking = ["gemma", "llama3.2", "qwen2.5", "mistral", "phi3"]
        return not any(x in model for x in non_thinking)
    if detect_is_minimax(base_url):
        return True
    return True


def build_chat_model() -> BaseChatModel:
    """根据 settings.LLM_PROVIDER 选择 ChatModel 实现

    - mock → MedicalMockChatModel
    - openai/ollama → MedicalOpenAIChatModel
    """
    provider = (settings.LLM_PROVIDER or "").lower().strip()
    if provider == "ollama" or provider == "openai":
        # Ollama 自动归一化为 openai 兼容协议
        if provider == "ollama" and (
            not settings.OPENAI_BASE_URL
            or "your-" in (settings.OPENAI_BASE_URL or "")
            or "api.openai.com" in (settings.OPENAI_BASE_URL or "")
        ):
            settings.OPENAI_BASE_URL = "http://localhost:11434/v1"
        if provider == "ollama" and (not settings.OPENAI_API_KEY or "your-" in settings.OPENAI_API_KEY):
            settings.OPENAI_API_KEY = "ollama"

        return MedicalOpenAIChatModel(
            model=settings.OPENAI_MODEL,
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY or "ollama",
            is_ollama=detect_is_ollama(),
            is_minimax=detect_is_minimax(),
            is_thinking_capable=detect_is_thinking_capable(),
        )

    # mock / 其他 / 兜底
    return MedicalMockChatModel()


# ====================== 消息转换工具 ======================

def _to_legacy(m: BaseMessage) -> Dict[str, str]:
    """langchain message → 原 llm_service 期望的 dict 形态"""
    if isinstance(m, SystemMessage):
        return {"role": "system", "content": m.content}
    if isinstance(m, HumanMessage):
        return {"role": "user", "content": m.content}
    if isinstance(m, AIMessage):
        return {"role": "assistant", "content": m.content}
    # 兜底:按 content 推断
    return {"role": "user", "content": getattr(m, "content", "")}


def _to_lc(m: BaseMessage) -> BaseMessage:
    """已经是 langchain 消息对象,直接透传(BaseChatModel.invoke 接受)"""
    return m


# ====================== JSON 解析工具(原 medical_agent 复用) ======================

def parse_json_response(raw: str) -> Dict[str, Any]:
    """从 LLM 响应中提取 JSON(原 medical_agent._parse_json_response 等价)"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {
        "reply": raw,
        "urgency_level": 2,
        "needs_urgent_care": False,
        "possible_causes": [],
        "suggested_examinations": [],
        "department": None,
        "self_care_tips": [],
    }
