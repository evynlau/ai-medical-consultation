"""LLM 服务 - 统一封装 OpenAI 兼容接口 + Mock"""
import json
import re
from typing import List, Dict, Optional, AsyncGenerator

from app.core.config import settings
from app.utils.logger import logger


class LLMService:
    """大模型调用服务
    - openai: 走 OpenAI 兼容 API(支持通义千问/智谱/deepseek 等)
    - mock: 内置规则引擎 + 模板,无 Key 也能跑
    """

    def __init__(self):
        # 归一化 provider: ollama 等同于 openai 兼容协议
        raw = (settings.LLM_PROVIDER or "").lower().strip()
        if raw == "ollama":
            self.provider = "openai"
            self._is_ollama = True
        else:
            self.provider = raw
            self._is_ollama = False
        self._client = None
        # Ollama 默认配置
        if self._is_ollama:
            if not settings.OPENAI_BASE_URL or "your-" in (settings.OPENAI_BASE_URL or "") or "api.openai.com" in settings.OPENAI_BASE_URL:
                settings.OPENAI_BASE_URL = "http://localhost:11434/v1"
            if not settings.OPENAI_API_KEY or "your-" in settings.OPENAI_API_KEY:
                settings.OPENAI_API_KEY = "ollama"  # Ollama 不校验 key,随便填

    def _get_client(self):
        if self._client is None and self.provider == "openai":
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY or "ollama",
                base_url=settings.OPENAI_BASE_URL,
                timeout=120.0,  # 本地模型推理慢,给 2 分钟
            )
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 1500,
        stream: bool = False,
    ) -> str:
        """通用聊天接口"""
        if self.provider == "mock":
            return self._mock_chat(messages)

        client = self._get_client()
        if client is None:
            logger.warning("[LLM] 客户端未初始化,降级到 mock")
            return self._mock_chat(messages)

        try:
            logger.info(f"[LLM] 调用 {self.provider} 模型: {settings.OPENAI_MODEL} @ {settings.OPENAI_BASE_URL}")
            if stream:
                return await self._stream_chat(client, messages, temperature, max_tokens)
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 1) 正常 content
            message = resp.choices[0].message
            content = (message.content or "").strip() if message.content else ""

            # 2) 思考型模型(Ollama 很多 MoE 会这样):content 空但 reasoning 有内容
            if not content:
                reasoning = getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None)
                if reasoning:
                    logger.info(f"[LLM] 检测到思考型模型,reasoning {len(reasoning)} 字符,提取最终答案")
                    content = self._extract_final_answer(reasoning)

            # 3) 如果还是空,降级到 mock(给用户看到东西,而不是空白气泡)
            if not content:
                logger.warning(f"[LLM] 响应为空(finish_reason={resp.choices[0].finish_reason}),降级到 mock")
                content = self._mock_chat(messages)

            logger.info(f"[LLM] 响应 {len(content)} 字符")
            return content
        except Exception as e:
            logger.error(f"[LLM] 调用失败: {type(e).__name__}: {e}")
            logger.error(f"[LLM] 检查项: 1) Ollama 是否运行? 2) 模型 '{settings.OPENAI_MODEL}' 是否已下载? 3) base_url '{settings.OPENAI_BASE_URL}' 是否可达?")
            # 失败也降级到 mock,不阻塞用户
            return self._mock_chat(messages)

    def _extract_final_answer(self, reasoning: str) -> str:
        """从思考型模型的 reasoning 中提取最终答案
        思路:reasoning 末尾通常有"Final Answer:"或"输出:"之类的标记,
              也可能直接包含 markdown 格式的最终答案
        """
        if not reasoning:
            return ""
        text = reasoning.strip()

        # 尝试 1:找"最终答案"等标记
        markers = ["最终答案", "最终输出", "Final Answer", "Final Output",
                   "输出如下", "输出:", "答案:", "回复如下", "应该回复",
                   "Ready to Output", "Final Response", "我会回复"]
        for m in markers:
            idx = text.find(m)
            if idx >= 0:
                # 取标记后到结尾的内容
                after = text[idx + len(m):].strip()
                # 去掉前缀标点
                for prefix in [":", "：", "=", "：", "应", "如下"]:
                    if after.startswith(prefix):
                        after = after[len(prefix):].strip()
                if len(after) > 20:  # 至少要有内容
                    return after

        # 尝试 2:取最后一段非空内容(>= 30 字)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p in reversed(paragraphs):
            # 跳过"思考过程"段落
            if any(k in p for k in ["thinking", "分析:", "Mental", "思考:", "让我", "Draft", "Self-Correction"]):
                continue
            if len(p) >= 30:
                return p

        # 兜底:取最后 800 字
        return text[-800:] if len(text) > 800 else text

    async def _stream_chat(self, client, messages, temperature, max_tokens) -> str:
        """流式接收后拼接(简单实现,WebSocket 走另一条路径)"""
        stream = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        chunks = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        return "".join(chunks)

    # ====================== Mock 实现 ======================

    def _mock_chat(self, messages: List[Dict[str, str]]) -> str:
        """Mock 回复:根据 system prompt 判断任务,套用模板
        支持:症状分析 / 自由对话 / 紧急识别 / 智能分诊
        """
        # 取最后一条 user 消息
        user_msg = ""
        for m in messages:
            if m.get("role") == "user":
                user_msg = m.get("content", "")

        upper = user_msg.upper()

        # 1. 智能分诊(请求字段少:urgency_label + reason)
        if "URGENCY_LABEL" in upper and "REASON" in upper:
            return self._mock_triage(user_msg)

        # 2. 结构化症状分析(详细 JSON)
        if "JSON" in upper and "URGENCY_LEVEL" in upper and "POSSIBLE_CAUSES" in upper:
            return self._mock_symptom_analysis(user_msg)

        # 3. 普通对话(把全部 messages 传过去,让 followup 能感知历史)
        return self._mock_general_chat(user_msg, "", messages)

    def _mock_general_chat(self, user_msg: str, system_msg: str, all_messages: List[Dict] = None) -> str:
        """通用对话模板 - 真正读取用户消息 + 感知历史"""
        all_messages = all_messages or [{"content": user_msg}]
        actual_user_msg = self._extract_patient_msg(user_msg)
        text = actual_user_msg.lower().strip()

        # 0. 极短回答(< 8 字)→ 走 followup
        neg_short = ["无", "没有", "没", "不知道", "不清楚", "没吃过", "没吃药", "没用药",
                     "其他无", "无其他", "无既往", "无既往病史"]
        if text in neg_short or len(text) <= 4:
            return self._mock_followup(all_messages, actual_user_msg)

        # Step 2: 寒暄 / 致谢 优先
        if any(k in text for k in ["你好", "您好", "hi ", "hello"]):
            return "您好,我是 AI 医学助手。请详细描述您的不适症状(如头痛、发热、咳嗽等),我会帮您分析。⚠️ 紧急情况请立即拨打 120。"

        if any(k in text for k in ["谢谢", "感谢", "多谢"]):
            return "不客气!请持续关注身体变化,有任何新症状或加重请及时复诊。保重!"

        # Step 3: 针对具体症状的科普/建议
        if any(k in text for k in ["感冒", "流感", "打喷嚏", "流鼻涕"]):
            return self._kb_reply("感冒", "感冒多为病毒感染,5-7 天可自愈。建议多休息、多饮水、清淡饮食;可对症服用复方感冒药。注意监测体温,如持续高热 > 3 天、出现呼吸困难或胸痛请立即就医。")

        if any(k in text for k in ["头痛", "头疼", "脑袋"]):
            return self._kb_reply("头痛", "头痛原因很多,常见如紧张性头痛、偏头痛、高血压、颈椎病等。**建议**:注意休息、避免长时间低头;监测血压;如为搏动性头痛、伴恶心呕吐或单侧明显,建议到**神经内科**就诊;如为剧烈突发头痛需立即就医排查脑血管意外。")

        if any(k in text for k in ["发热", "发烧", "体温", "高热"]):
            return self._kb_reply("发热", "发热是身体对抗感染的信号。**居家处理**:多饮水、物理降温、> 38.5°C 可服用对乙酰氨基酚或布洛芬。**就医指征**:> 39°C 持续 3 天不退、伴呼吸困难/胸痛/意识改变、或基础病加重,建议到**发热门诊/呼吸内科**就诊。")

        if any(k in text for k in ["咳嗽", "咳痰", "有痰"]):
            return self._kb_reply("咳嗽", "咳嗽常见于上呼吸道感染、急性支气管炎等。**建议**:多饮温水、避免冷空气刺激;干咳可用右美沙芬,有痰可用氨溴索。**就医指征**:咳黄脓痰 > 1 周、伴喘息或呼吸困难、痰中带血,建议到**呼吸内科**就诊,必要时查胸片。")

        if any(k in text for k in ["腹痛", "肚子痛", "胃痛", "胃部", "腹泻", "拉肚子"]):
            return self._kb_reply("腹痛/腹泻", "常见原因:急性胃肠炎、饮食不当、功能性消化不良等。**建议**:清淡流食(米粥、面条)、口服补液盐防脱水、避免油腻辛辣。**就医指征**:剧烈持续腹痛、便血/黑便、高热、脱水症状(口干尿少),建议到**消化内科**就诊。")

        if any(k in text for k in ["胸痛", "心绞痛", "心悸", "心慌"]):
            return self._kb_reply("胸痛/心悸", "⚠️ **胸痛是危险症状**。可能涉及心绞痛、心肌梗死、肋间神经痛、反流性食管炎等。**立即拨打 120 的情况**:胸骨后压榨样疼痛 > 15 分钟、伴大汗/恶心/濒死感、放射至左肩左臂、硝酸甘油不缓解。心悸频繁或伴胸痛、晕厥,也建议到**心血管内科**尽快就诊。")

        if any(k in text for k in ["血压", "头晕", "眩晕", "低血压", "偏高"]):
            return self._kb_reply("血压/头晕", "血压偏低(100/55)若无症状可观察,建议定期监测、避免突然起身。**头晕**原因多样:低血压、低血糖、贫血、耳石症、颈椎病等。**建议**:起床缓慢、保证睡眠、均衡饮食;如头晕反复发作伴视物旋转、肢体麻木,建议到**神经内科**或**心血管内科**就诊,排查血压/血常规/颈椎等问题。")

        if any(k in text for k in ["过敏", "皮疹", "瘙痒", "湿疹", "荨麻疹"]):
            return self._kb_reply("过敏/皮疹", "常见于过敏性皮炎、荨麻疹、湿疹。**建议**:避免搔抓、保持皮肤清洁干燥;可口服抗组胺药(西替利嗪、氯雷他定);外用炉甘石洗剂。**就医指征**:皮疹迅速扩大、伴呼吸困难/口唇肿胀(警惕过敏性休克)、持续 > 1 周不缓解,建议到**皮肤科**就诊,必要时查过敏原。")

        if any(k in text for k in ["失眠", "睡不着", "睡眠差", "焦虑", "抑郁"]):
            return self._kb_reply("失眠/情绪", "失眠和情绪问题往往互为因果。**建议**:规律作息、睡前避免咖啡和电子屏幕、适度运动、必要时寻求心理支持。如持续 > 2 周影响生活,建议到**心理科/精神科**就诊,不要讳疾忌医。")

        if any(k in text for k in ["吃什么", "忌口", "饮食"]):
            return "生病期间建议:清淡易消化饮食,多饮温水,避免辛辣、油腻、生冷食物。保证优质蛋白摄入(蛋、奶、鱼),多吃蔬菜水果。"

        if any(k in text for k in ["药", "吃什么药", "用药", "能吃", "可以吃"]):
            return "用药建议需结合具体症状和过敏史,**不能一概而论**。常见安全选择:解热镇痛(对乙酰氨基酚、布洛芬)、止咳化痰(氨溴索)、抗过敏(西替利嗪)等。具体用药请咨询医生或药师,避免自行同时使用多种复方感冒药导致成分过量。"

        # 兜底:基于对话轮次,推进问诊
        return self._mock_followup(all_messages or [{"content": user_msg}], actual_user_msg)

    def _extract_patient_msg(self, user_msg: str) -> str:
        """从 prompt 中提取真正的用户消息,剥离 RAG 上下文"""
        m = re.search(r"患者说[::]\s*(.+?)$", user_msg, re.DOTALL)
        if m:
            return m.group(1).strip()
        return user_msg.strip()

    def _kb_reply(self, topic: str, body: str) -> str:
        return f"关于 **{topic}** 的科普与建议:\n\n{body}\n\n⚠️ 以上仅供参考,具体诊疗请咨询医生。"

    def _mock_followup(self, all_messages: List[Dict], actual_user_msg: str) -> str:
        """根据历史对话判断下一步该问什么"""
        asked_text = " ".join(
            m.get("content", "") for m in all_messages
            if m.get("role") == "assistant"
        ).lower()
        user_text = " ".join(
            m.get("content", "") for m in all_messages
            if m.get("role") == "user"
        ).lower()

        already_asked_duration = any(p in asked_text for p in ["持续多久", "几天了", "持续时间", "持续了", "多长时间"])
        already_asked_accompany = any(p in asked_text for p in ["其他不舒服", "伴随", "还有没有", "有无其他", "其他症状"])
        already_asked_history = any(p in asked_text for p in ["既往", "慢性病", "过敏史", "病史"])
        already_asked_medication = any(p in asked_text for p in ["用过什么药", "在服", "吃什么药", "最近用药"])
        info_complete = "基础信息已收集" in asked_text

        echo = f"您提到「{actual_user_msg[:60]}」,我记下了。\n\n" if actual_user_msg else ""

        if info_complete:
            return echo + "还有什么想补充的吗?\n\n如果暂时没有,可以直接点右上角「**结构化分析**」,我会给出综合判断。"

        if not already_asked_duration:
            return echo + "**请问这个症状持续多久了?** (如 1 天、3 天、数周)\n\n这有助于判断是急性还是慢性问题。回复「3 天」「一周」等均可。"
        if not already_asked_accompany:
            return echo + "**请问除了主要症状,还有其他不舒服吗?**\n\n比如:发热、乏力、食欲不振、恶心、出汗等。\n\n如果完全无伴随症状,请回复「无」即可。"
        if not already_asked_history:
            return echo + "**请问既往有什么慢性病或长期用药吗?**\n\n比如:高血压、糖尿病、冠心病、过敏史等。\n\n如无,请回复「无既往病史」。"
        if not already_asked_medication:
            return echo + "**请问最近用过什么药吗?** (含处方药、感冒药、中药)\n\n如未服药,请回复「没吃药」。"

        return (
            echo +
            "✅ **基础信息已收集**。\n\n"
            "**下一步建议**:\n"
            "1. 点击「**结构化分析**」,我会给出系统性的可能病因 + 建议科室\n"
            "2. 或继续描述任何你想到的细节(比如诱因、缓解因素等)\n"
            "3. 如果症状有变化,随时告诉我\n\n"
            "⚠️ 本 AI 仅供参考,不能替代专业医生诊断。如有不适,请及时就医。"
        )

    def _mock_triage(self, user_msg: str) -> str:
        """生成模拟的智能分诊 JSON
        只匹配用户实际症状,不要被知识库内容误导
        """
        # 提取"症状:" 后到"参考知识"前的内容
        text = user_msg.lower()
        m = re.search(r"症状[::]\s*(.+?)(?:\n\n参考|\n参考|$)", user_msg, re.DOTALL)
        symptom_text = m.group(1).lower() if m else text

        urgent = any(k in symptom_text for k in ["胸痛", "心绞痛", "呼吸困难", "大出血", "昏迷"])

        department = "全科医学科"
        urgency = 2
        urgency_label = "择期就医"
        reason = "症状较轻,可择期到门诊就诊"

        if any(k in symptom_text for k in ["胸痛", "心绞痛", "心悸"]):
            department = "心血管内科"; urgency = 4 if urgent else 3
            urgency_label = "立即急诊" if urgency == 4 else "尽快就医"
            reason = "胸痛可能涉及心源性病因,需尽快明确"
        elif any(k in symptom_text for k in ["头痛", "头疼", "头胀"]):
            department = "神经内科"
            urgency = 4 if "剧烈" in symptom_text else 2
            urgency_label = "立即急诊" if urgency == 4 else "择期就医"
            reason = "头痛原因多样,需结合病史判断"
        elif any(k in symptom_text for k in ["腹痛", "胃痛", "腹泻", "胃部"]):
            department = "消化内科"; urgency = 2
            urgency_label = "择期就医"
            reason = "消化道症状,建议消化内科就诊"
        elif any(k in symptom_text for k in ["发热", "发烧", "咳嗽", "咽痛"]):
            department = "呼吸内科"; urgency = 3 if "高热" in symptom_text else 2
            urgency_label = "尽快就医" if urgency == 3 else "择期就医"
            reason = "呼吸道感染表现,需鉴别类型"
        elif any(k in symptom_text for k in ["皮疹", "瘙痒", "过敏"]):
            department = "皮肤科"; urgency = 2; urgency_label = "择期就医"
            reason = "皮肤问题,建议皮肤科就诊"
        elif any(k in symptom_text for k in ["血压", "头晕"]):
            department = "心血管内科"; urgency = 2; urgency_label = "择期就医"
            reason = "建议监测血压,排查心血管原因"

        return json.dumps({
            "department": department,
            "urgency_level": urgency,
            "urgency_label": urgency_label,
            "reason": reason,
        }, ensure_ascii=False, indent=2)

    def _mock_symptom_analysis(self, user_msg: str) -> str:
        """生成模拟的症状分析 JSON
        只匹配用户实际症状,不要被知识库内容误导
        """
        # 提取"【患者症状】" 后到"【相关医学知识】"前的内容
        m = re.search(r"【患者症状】\s*(.+?)(?:\n\n【相关医学|\n【相关医学|$)", user_msg, re.DOTALL)
        if m:
            text = m.group(1).lower()
        else:
            text = user_msg.lower()
        # 紧急识别
        urgent = any(k in text for k in [
            "胸痛", "心绞痛", "呼吸困难", "大出血", "昏迷", "意识不清",
            "剧烈头痛", "突发", "中风", "瘫痪", "休克", "自杀",
        ])

        causes = []
        exams = []
        tips = []
        department = "全科医学科"
        urgency = 2

        if any(k in text for k in ["胸痛", "心绞痛", "心悸", "心慌"]):
            causes = ["心绞痛", "肋间神经痛", "反流性食管炎", "肌肉拉伤"]
            exams = ["心电图", "心肌酶谱", "胸部X线"]
            department = "心血管内科"
            urgency = 4 if urgent else 3
        elif any(k in text for k in ["头痛", "头疼", "头胀"]):
            causes = ["紧张性头痛", "偏头痛", "高血压性头痛", "颈椎病"]
            exams = ["血压监测", "头颅CT(必要时)", "颈椎X线"]
            department = "神经内科"
            urgency = 4 if "剧烈" in text else 2
        elif any(k in text for k in ["腹痛", "肚子痛", "胃痛", "腹泻"]):
            causes = ["急性胃肠炎", "功能性消化不良", "肠易激综合征"]
            exams = ["腹部B超", "血常规", "粪便常规"]
            department = "消化内科"
            urgency = 2
        elif any(k in text for k in ["发热", "发烧", "体温"]):
            causes = ["上呼吸道感染", "细菌性感冒", "流感"]
            exams = ["血常规", "C反应蛋白", "体温监测"]
            department = "发热门诊/呼吸内科"
            urgency = 3 if "高热" in text or "持续" in text else 2
        elif any(k in text for k in ["咳嗽", "咽痛", "喉咙痛"]):
            causes = ["急性咽炎", "急性支气管炎", "上呼吸道感染"]
            exams = ["血常规", "胸片(必要时)"]
            department = "呼吸内科"
            tips = ["多饮温水", "注意休息", "避免辛辣刺激食物"]
        elif any(k in text for k in ["皮疹", "瘙痒", "过敏"]):
            causes = ["过敏性皮炎", "荨麻疹", "湿疹"]
            exams = ["过敏原检测", "血常规"]
            department = "皮肤科"
        else:
            causes = ["需进一步检查明确"]
            exams = ["建议先到全科或内科就诊"]
            department = "全科医学科"

        tips = [
            "注意休息,保证充足睡眠",
            "饮食清淡,多饮温水",
            "如症状加重或出现新症状,请及时就医",
        ]

        result = {
            "reply": self._build_mock_reply(department, urgency, causes, exams, tips, urgent),
            "urgency_level": urgency,
            "needs_urgent_care": urgent or urgency >= 4,
            "possible_causes": causes,
            "suggested_examinations": exams,
            "department": department,
            "self_care_tips": tips,
            "disclaimer": "本分析仅供参考,不能替代专业医生诊断。如有不适,请及时就医。",
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _build_mock_reply(self, department, urgency, causes, exams, tips, urgent) -> str:
        """组装面向用户的回复文字"""
        urgent_warn = "⚠️ 检测到可能的紧急症状,建议立即就医或拨打 120。\n\n" if urgent else ""
        return (
            f"{urgent_warn}根据您描述的症状,我为您做了初步分析。\n\n"
            f"**可能涉及科室**:{department or '建议先到全科就诊'}\n\n"
            f"**可能的原因(仅供参考)**:\n" +
            "\n".join(f"- {c}" for c in causes) + "\n\n" +
            f"**建议检查**:\n" + "\n".join(f"- {e}" for e in exams) + "\n\n" +
            f"**日常护理**:\n" + "\n".join(f"- {t}" for t in tips) + "\n\n"
            "⚠️ 本分析仅供参考,不能替代专业医生诊断。如有不适,请及时就医。"
        )



# 单例
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
