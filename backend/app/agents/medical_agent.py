"""Medical Agent - 医疗问诊智能体核心"""
import json
import re
from typing import List, Dict, Optional, Any

from app.services.llm_service import get_llm_service, LLMService
from app.services.rag_service import get_rag_service
from app.utils.logger import logger


# 紧急症状关键词
URGENT_KEYWORDS = [
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

URGENT_REGEX = re.compile("|".join(URGENT_KEYWORDS))


class MedicalAgent:
    """医疗问诊智能体"""

    def __init__(self):
        self.llm = get_llm_service()
        self.rag = get_rag_service()

    # ====================== 系统提示 ======================

    def _build_system_prompt(self, user_context: Optional[Dict] = None) -> str:
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

    # ====================== 紧急识别 ======================

    def detect_emergency(self, text: str) -> bool:
        return bool(URGENT_REGEX.search(text))

    # ====================== 症状分析 ======================

    async def analyze_symptoms(
        self, symptoms: str, user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """结构化症状分析"""
        # 1. 紧急检测
        is_emergency = self.detect_emergency(symptoms)

        # 2. RAG 检索
        try:
            rag_results = self.rag.hybrid_search(query=symptoms, top_k=5)
        except Exception as e:
            logger.warning(f"RAG 检索失败,降级到无知识库模式: {e}")
            rag_results = []

        # 3. 组装上下文
        knowledge_text = ""
        if rag_results:
            knowledge_text = "\n\n【相关医学知识参考】\n"
            for i, doc in enumerate(rag_results, 1):
                content = doc.get("content", "")[:500]
                knowledge_text += f"\n{i}. 《{doc.get('title', '医学知识')}》({doc.get('category', '')})\n{content}\n"

        # 4. LLM 分析
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
            {"role": "system", "content": self._build_system_prompt(user_context)},
            {"role": "user", "content": analysis_prompt},
        ]
        raw = await self.llm.chat(messages, temperature=0.3, max_tokens=1500)

        # 5. 解析 + 清洗 reply
        result = self._parse_json_response(raw)
        if result.get("reply"):
            result["reply"] = self._clean_reply(result["reply"])
        if is_emergency and not result.get("needs_urgent_care"):
            result["needs_urgent_care"] = True
            result["urgency_level"] = max(result.get("urgency_level", 3), 4)

        # 6. 附加来源
        result["reference_sources"] = [
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "category": r.get("category"),
                "relevance": round(r.get("score", 0), 3),
            }
            for r in rag_results[:3]
        ]

        return result

    # ====================== 多轮对话 ======================

    async def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        user_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """多轮对话模式"""
        # 1. 紧急检测
        is_emergency = self.detect_emergency(user_message)

        # 2. RAG 检索(只用当前问题)
        try:
            rag_results = self.rag.hybrid_search(query=user_message, top_k=3)
        except Exception as e:
            logger.warning(f"RAG 检索失败: {e}")
            rag_results = []

        # 3. 知识摘要
        knowledge_text = ""
        if rag_results:
            knowledge_text = "\n【相关知识】\n"
            for i, doc in enumerate(rag_results, 1):
                content = doc.get("content", "")[:300]
                knowledge_text += f"{i}. {doc.get('title', '')}: {content}\n"

        # 4. 组装消息
        messages = [{"role": "system", "content": self._build_system_prompt(user_context)}]
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # 5. 当前消息
        if is_emergency:
            prefix = "⚠️ 检测到可能的紧急症状,请先提示用户立即就医,然后再给建议。\n\n"
        else:
            prefix = ""

        current_msg = f"{prefix}参考知识:{knowledge_text}\n\n患者说:{user_message}"
        messages.append({"role": "user", "content": current_msg})

        # 6. 调用
        reply = await self.llm.chat(messages, temperature=0.5, max_tokens=1200)

        return {
            "reply": reply,
            "is_emergency": is_emergency,
            "urgency_level": 4 if is_emergency else 2,
            "source_knowledge": [
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "category": r.get("category"),
                    "content_preview": r.get("content", "")[:200],
                    "relevance": round(r.get("score", 0), 3),
                }
                for r in rag_results[:3]
            ],
        }

    # ====================== 智能分诊 ======================

    async def triage(self, symptoms: str) -> Dict[str, Any]:
        """快速分诊(轻量级,只需科室+紧急度)"""
        is_emergency = self.detect_emergency(symptoms)
        try:
            rag_results = self.rag.hybrid_search(query=symptoms, top_k=3)
        except Exception:
            rag_results = []

        knowledge_text = ""
        if rag_results:
            knowledge_text = "\n参考知识:\n"
            for d in rag_results:
                knowledge_text += f"- {d.get('title', '')}: {d.get('content', '')[:200]}\n"

        prompt = f"""根据患者症状,快速给出分诊建议。

症状:{symptoms}
{knowledge_text}

请用 JSON 输出:
{{
  "department": "推荐科室",
  "urgency_level": 1-4,
  "urgency_label": "文字说明(立即急诊/尽快就医/择期就医/无需就医)",
  "reason": "推荐理由(1-2 句)"
}}"""

        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        raw = await self.llm.chat(messages, temperature=0.2, max_tokens=600)
        result = self._parse_json_response(raw)
        if is_emergency and result.get("urgency_level", 0) < 4:
            result["urgency_level"] = 4
            result["urgency_label"] = "立即急诊"
        result["reference_sources"] = [
            {"title": r.get("title"), "relevance": round(r.get("score", 0), 3)}
            for r in rag_results[:3]
        ]
        return result

    # ====================== 工具方法 ======================

    def _clean_reply(self, text: str) -> str:
        """委托给 LLM 服务层统一清洗(保证所有出口行为一致)"""
        return LLMService._clean_reply(text)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # 尝试从 ```json ... ``` 代码块中提取
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试提取第一个 {...} 块
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        # 兜底
        return {
            "reply": raw,
            "urgency_level": 2,
            "needs_urgent_care": False,
            "possible_causes": [],
            "suggested_examinations": [],
            "department": None,
            "self_care_tips": [],
        }


# 单例
_agent: MedicalAgent | None = None


def get_medical_agent() -> MedicalAgent:
    global _agent
    if _agent is None:
        _agent = MedicalAgent()
    return _agent
