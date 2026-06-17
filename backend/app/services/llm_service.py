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
        else:
            self.provider = raw
        self._client = None
        # Ollama 默认配置
        if self._is_ollama():
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
                timeout=float(settings.API_RESPONSE_TIMEOUT),
            )
        return self._client

    # ===== Provider 特性探测 =====
    def _is_ollama(self) -> bool:
        """是否为 Ollama(通过 base_url 判定)"""
        url = (settings.OPENAI_BASE_URL or "").lower()
        return "11434" in url and "/v1" in url

    def _is_minimax(self) -> bool:
        """是否为 MiniMax API(通过 base_url 判定)"""
        url = (settings.OPENAI_BASE_URL or "").lower()
        return "minimaxi" in url or "minimax" in url

    def _is_thinking_capable(self) -> bool:
        """当前 provider + model 是否可能输出 thinking 字段
        - Ollama: 多数 MoE/思考型模型(关键词)会输出 reasoning
        - MiniMax: 默认思考,需显式 disable
        - 其他: 保守按"会"处理
        """
        if self._is_ollama():
            model = (settings.OPENAI_MODEL or "").lower()
            # 已知的非思考型 Ollama 模型
            non_thinking = ["gemma", "llama3.2", "qwen2.5", "mistral", "phi3"]
            return not any(x in model for x in non_thinking)
        if self._is_minimax():
            return True
        # OpenAI / 其他:保守返回 True(让清洗兜底)
        return True

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 1500,
        stream: bool = False,
        disable_thinking: Optional[bool] = None,
    ) -> str:
        """通用聊天接口
        disable_thinking:
          - None(默认): 按 provider 自动决定
            · Ollama  → 注入 think=False(让 Ollama 跳过内部思考)
            · MiniMax → 注入 extra_body={"thinking": {"type": "disabled"}}
            · 其他   → 不动
          - True:  强制关闭
          - False: 强制开启(不传任何禁用参数)
        """
        if self.provider == "mock":
            return self._mock_chat(messages)

        client = self._get_client()
        if client is None:
            logger.warning("[LLM] 客户端未初始化,降级到 mock")
            return self._mock_chat(messages)

        # 决定是否尝试关闭思考
        if disable_thinking is None:
            want_disable = self._is_thinking_capable() and (self._is_ollama() or self._is_minimax())
        else:
            want_disable = disable_thinking and self._is_thinking_capable()

        # 构造透传给 provider 的参数
        extra_kwargs: Dict[str, Any] = {}
        if want_disable:
            if self._is_ollama():
                # Ollama 0.6+ 支持 think=False 跳过 thinking
                extra_kwargs["think"] = False
            elif self._is_minimax():
                # MiniMax 通过 extra_body 注入 vendor-specific 参数
                extra_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        try:
            logger.info(
                f"[LLM] 调用 {self.provider} 模型: {settings.OPENAI_MODEL} @ {settings.OPENAI_BASE_URL}"
                f"{' (disable_thinking=True)' if want_disable else ''}"
            )
            if stream:
                return await self._stream_chat(client, messages, temperature, max_tokens)
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra_kwargs,
            )

            # 1) 正常 content
            message = resp.choices[0].message
            content = (message.content or "").strip() if message.content else ""
            reasoning = getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None) or ""
            is_thinking_model = bool(reasoning)

            # 2) 思考型模型(Ollama 很多 MoE):同时有 content 和 reasoning
            #    content 才是用户要的输出,reasoning 是思考过程(可丢弃)
            if is_thinking_model:
                logger.info(f"[LLM] 思考型模型(content={len(content)}字, reasoning={len(reasoning)}字)")
                if content:
                    # content 已有,直接用,reasoning 丢弃
                    logger.info(f"[LLM] 思考型已返回 content,使用 content")
                else:
                    # content 为空才去 reasoning 找答案
                    logger.info(f"[LLM] content 为空,从 reasoning 提取")
                    content = self._extract_final_answer(reasoning) or content

            # 3) 都没内容,降级 mock
            if not content:
                logger.warning(f"[LLM] 响应为空(finish_reason={resp.choices[0].finish_reason}),降级到 mock")
                content = self._mock_chat(messages)

            # 4) 全局清洗:剥掉思考型模型的残留(Check against / Draft JSON / 我将回复等)
            content = self._clean_reply(content)

            logger.info(f"[LLM] 响应 {len(content)} 字符")
            return content
        except Exception as e:
            logger.error(f"[LLM] 调用失败: {type(e).__name__}: {e}")
            logger.error(f"[LLM] 检查项: 1) Ollama 是否运行? 2) 模型 '{settings.OPENAI_MODEL}' 是否已下载? 3) base_url '{settings.OPENAI_BASE_URL}' 是否可达?")
            return self._mock_chat(messages)

    @staticmethod
    def _clean_reply(text: str) -> str:
        """清洗 LLM 响应,剥掉思考型模型的自检/规划残留
        用于所有出口:chat / analyze / triage,确保前端拿到的都是最终答案
        """
        import re
        if not text:
            return text

        # 0) 整段剥掉 <think>...</think> 块(Ollama 0.6+ 思考型模型会用此标签包裹 reasoning)
        #    注意:多行、嵌套、标签对大小写、HTML 实体(&lt; 等)都处理
        for tag in ("think", "thinking", "reasoning", "reflection"):
            for open_tag, close_tag in (
                (f"<{tag}>", f"</{tag}>"),
                (f"<{tag.title()}>", f"</{tag.title()}>"),
                (f"&lt;{tag}&gt;", f"&lt;/{tag}&gt;"),
            ):
                # 标准配对
                text = re.sub(open_tag + r".*?" + close_tag, "", text, flags=re.DOTALL | re.IGNORECASE)
                # 仅有开标签无闭标签:切掉之后
                text = re.sub(open_tag + r".*$", "", text, flags=re.DOTALL | re.IGNORECASE)

        # 1) 截断"Check against Constraints"等标记
        #    注意顺序:越具体、越长的 pattern 放前面,避免短 pattern 误切
        cut_markers = [
            # === 高优先级:精确匹配"Draft"开头的 plan 标题 ===
            r"\n\s*\d+\.\s+\*\*Draft\b",  # 4.  **Draft - Section by Section
            r"\n\s*\d+\.\s+\*\*Plan\b",
            r"\n\s*\d+\.\s+\*\*Outline\b",
            # === 中优先级:思考型模型常见自检/规划文本 ===
            r"\n\s*Check against Constraints[:：]?",
            r"\n\s*Check against constraints[:：]?",
            r"\n\s*Draft JSON",
            r"\n\s*Map to JSON",
            r"\n\s*Structure JSON[:：]?",
            r"\n\s*Final Polish[:：]?",
            r"\n\s*Self[- ]Correction",
            r"\n\s*Mental Refinement[:：]?",  # 这个会切到 (Mental Refinement) 之前
            r"\n\s*Ready to Output",
            r"\n\s*Output Format[:：]?",
            r"\n\s*Constraints?[:：]?",
            r"\n\s*Self[- ]?Verify",
            r"\n\s*Let'?s? structure",
            r"\n\s*Draft\s*[-:]",
            r"\n\s*Outline\s*[-:]",
            r"\n\s*Plan\s*[-:]",
            r"\n\s*Format\s*Output",
            r"\n\s*Format\s*[-:]",
            r"\n\s*Tone\s*[-:]",
            r"\n\s*Length\s*[-:]",
            r"\n\s*Structure\s*[-:]",
            # 思考型模型常见的"开场白"
            r"^All (?:fields|the) (?:match|are)",
            r"^I will (?:format|output|generate)",
            r"^I need to (?:make sure|format|ensure|check)",
            r"^The prompt asks? for",
            r"^This (?:response|answer) (?:is|will)",
            r"^I will output only the",
            r"^I'll output",
            r"^Here's? (?:the|my|a) (?:JSON|response|answer)",
            r"^Let me (?:check|verify|think|generate)",
            r"^Now I (?:will|need|can)",
            r"^This is a",
            r"^The (?:output|format) (?:is|should|must)",
            # 段落内的英文注释块 `*(Acknowledge)*` `*(Common Causes)*`
            r"\*\([A-Za-z][^)]*\)\*",  # 匹配 *(English Comment)*
        ]
        for pat in cut_markers:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                text = text[:m.start()].rstrip()
                break

        # 2) 检测整个内容是否就是"thinking narration"(没实际内容)
        medical_keywords = ["建议", "就医", "检查", "症状", "治疗", "风险", "患者", "健康", "疾病", "注意", "可能", "你好", "您好"]
        if len(text) < 50 and not any(k in text for k in medical_keywords):
            return ""  # 整段都是 thinking narration,丢弃

        # 3) 清理 markdown 残留(```json 等代码块标记)
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*", "", text)

        # 4) 清理"行内英文标签" `*General Advice:*` `*Disclaimer:*` 等
        text = re.sub(r"\*[A-Za-z][^*\n]{1,40}:\*", "", text)
        # 清理孤儿单星号(避免残留 "Advice:" 等)
        text = re.sub(r"\s\*\s+", " ", text)
        # 清理 markdown 加粗标记 `**xxx**` (但保留普通文本)
        # 这里只去掉单独成对的 `**`(被外层剥剩的)
        text = re.sub(r"\*\*\s*\*\*", "", text)

        return text.strip()

    def _extract_final_answer(self, reasoning: str) -> str:
        """从思考型模型的 reasoning 中提取最终答案
        优先级:
          1) reasoning 中内嵌的 ```json ... ``` 代码块(结构化输出场景)
          2) 纯 JSON {...}(无代码块包裹)
          3) "最终答案/Final Answer" 标记后的内容
          4) 过滤"思考残留"后,取最后一段非空内容
          5) 全文末尾 800 字(兜底)
        """
        if not reasoning:
            return ""

        import re

        # 0) 优先:reasoning 中可能内嵌 ```json {...}``` 代码块
        json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", reasoning, re.DOTALL)
        for blk in reversed(json_blocks):
            if '"reply"' in blk or '"urgency_level"' in blk or '"department"' in blk:
                return blk.strip()

        # 0.5) 任意完整 JSON 对象
        brace_match = re.search(r'(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})', reasoning, re.DOTALL)
        if brace_match:
            candidate = brace_match.group(1)
            if any(k in candidate for k in ['"reply"', '"urgency_level"', '"department"', '"possible_causes"']):
                return candidate

        text = reasoning.strip()

        # 1) "最终答案"等标记
        markers = ["最终答案", "最终输出", "Final Answer", "Final Output",
                   "输出如下", "输出:", "答案:", "回复如下", "应该回复",
                   "Ready to Output", "Final Response", "我会回复"]
        for m in markers:
            idx = text.find(m)
            if idx >= 0:
                after = text[idx + len(m):].strip()
                for prefix in [":", "：", "=", "应", "如下"]:
                    if after.startswith(prefix):
                        after = after[len(prefix):].strip()
                if len(after) > 20:
                    return after

        # 2) 过滤"思考残留"行,选最像"中文医学答案"的段落
        #    启发式:中文段落中文字符占比高,英文模板段落中文字符占比低
        #    思考型模型在 reasoning 末尾常是英文自检,不是答案
        raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p) >= 30]

        # 2.1) 剥掉段落开头的 markdown 标题行(如 "5.  **Draft the Content...:**" 单独成段的情况)
        cleaned_paragraphs = []
        title_pattern = re.compile(r"^\d+\.\s+\*\*[A-Za-z][^*]*\*\*[:：]?\s*$")
        for p in raw_paragraphs:
            lines = p.split("\n")
            # 去掉首行如果是纯标题
            if lines and title_pattern.match(lines[0].strip()):
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()
            if len(cleaned) >= 30:
                cleaned_paragraphs.append(cleaned)

        def chinese_ratio(s):
            n_zh = sum(1 for ch in s if "一" <= ch <= "鿿")
            return n_zh / max(len(s), 1)

        # 优先选"中文密度 ≥ 30% 且长度 ≥ 50"的段落
        candidates = [p for p in cleaned_paragraphs if chinese_ratio(p) >= 0.3 and len(p) >= 50]
        if candidates:
            return max(candidates, key=len)

        # 退化:无明显中文段落,试英文中"看起来最像答案"的那段
        # 跳过明显的 planning/draft/checking 段
        skip_patterns = [
            "check schema", "all match", "analyze user input", "thinking process",
            "self-correction", "mental refinement", "draft", "let me",
            "map to json", "constraints:", "output format", "final polish",
            "ready to", "ready for", "我能想到", "让我", "思考:", "分析:",
            "drafting", "preparation", "constraint", "step 1", "step 2",
            "step 3", "step 4", "step 5", "6.", "7.", "8.", "9.", "10.",
            "我需要", "1.", "2.", "3.", "4.", "5.", "**",
            "## section", "## subsection",
        ]
        # 反向找第一段非 thinking 的
        for p in reversed(paragraphs):
            p_lower = p.lower()
            if any(s in p_lower for s in skip_patterns):
                continue
            if len(p) >= 30:
                return p

        # 3) 兜底:取最后 800 字
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


# ========== 模块级工具函数(供 OCR / imaging / 影像验证复用) ==========

def _detect_is_ollama(base_url: str = "") -> bool:
    url = (base_url or settings.OPENAI_BASE_URL or "").lower()
    return "11434" in url and "/v1" in url


def _detect_is_minimax(base_url: str = "") -> bool:
    url = (base_url or settings.OPENAI_BASE_URL or "").lower()
    return "minimaxi" in url or "minimax" in url


def _is_thinking_capable_model(model_name: str = "", base_url: str = "") -> bool:
    """判断当前 model + provider 是否会输出 thinking 字段(模块级)"""
    if _detect_is_ollama(base_url):
        model = (model_name or settings.OPENAI_MODEL or "").lower()
        non_thinking = ["gemma", "llama3.2", "qwen2.5", "mistral", "phi3"]
        return not any(x in model for x in non_thinking)
    if _detect_is_minimax(base_url):
        return True
    return True  # 其他保守返回 True


def build_thinking_disable_kwargs(model_name: str = "", base_url: str = "", force_disable: bool = True) -> dict:
    """构造用于关闭 thinking 的额外参数
    - Ollama: think=False
    - MiniMax: extra_body={"thinking": {"type": "disabled"}}
    - 其他: 返回空 dict
    返回: {**kwargs} 透传给 client.chat.completions.create()
    """
    if not force_disable:
        return {}
    if not _is_thinking_capable_model(model_name, base_url):
        return {}
    if _detect_is_ollama(base_url):
        return {"think": False}
    if _detect_is_minimax(base_url):
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}
