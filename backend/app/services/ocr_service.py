"""OCR 服务 - 抽象多种 OCR 引擎
- vision(主): 多模态 LLM 直接读图(Ollama llama3.2-vision / qwen2-vl / OpenAI GPT-4V)
- tesseract(备): 本地 tesseract-ocr,需装系统包
- mock(降级): 返回演示文本
"""
import os
import re
import json
import hashlib
import base64
import mimetypes
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.config import settings
from app.utils.logger import logger

UPLOAD_DIR = Path("./data/ocr_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class OCRService:
    """OCR 抽象服务"""

    def __init__(self):
        # 按可用性自动选
        cfg = (settings.OCR_ENGINE or "auto").lower()
        if cfg == "vision":
            self.engine = "vision"
        elif cfg == "tesseract":
            self.engine = "tesseract" if self._check_tesseract() else "mock"
        elif cfg == "mock":
            self.engine = "mock"
        else:  # auto
            if self._check_vision_llm():
                self.engine = "vision"
            elif self._check_tesseract():
                self.engine = "tesseract"
            else:
                self.engine = "mock"
        logger.info(f"[OCR] 引擎选择: {self.engine} (configured: {cfg})")

    def _check_tesseract(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.debug(f"[OCR] tesseract 不可用: {e}")
            return False

    def _check_vision_llm(self) -> bool:
        """检查是否配置了可用的视觉 LLM
        - mock 模式不算
        - 需要非 mock 模式 + 已配置 base_url/api_key
        """
        if settings.LLM_PROVIDER == "mock":
            return False
        # 必须有 base_url,即使是 ollama 也要有
        return bool(settings.OPENAI_BASE_URL) and settings.OPENAI_BASE_URL != "https://api.openai.com/v1" or bool(settings.OPENAI_API_KEY) and settings.OPENAI_API_KEY not in ("", "your-openai-api-key", "ollama")

    def recognize(self, file_path: str, image_type_hint: str = "") -> Dict[str, Any]:
        if self.engine == "vision":
            return self._recognize_vision(file_path, image_type_hint)
        elif self.engine == "tesseract":
            return self._recognize_tesseract(file_path, image_type_hint)
        else:
            return self._recognize_mock(file_path, image_type_hint)

    def _recognize_vision(self, file_path: str, image_type_hint: str) -> Dict[str, Any]:
        """用多模态 LLM 读图
        一次调用完成 OCR(返回原文本)+ 简化的结构化提示

        关键:在独立线程里跑 asyncio.run(),避免与 uvicorn 的 uvloop 冲突
        (uvloop.Loop 不能被 nest_asyncio patch)
        """
        try:
            from openai import AsyncOpenAI
            from app.core.config import settings

            model = settings.OCR_VISION_MODEL or settings.OPENAI_MODEL
            logger.info(f"[OCR] 调用 vision 模型: {model} (image: {Path(file_path).stat().st_size//1024}KB)")

            # 编码图片为 base64 data URL
            mime, _ = mimetypes.guess_type(file_path)
            if not mime:
                mime = "image/png"
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"

            prompt = f"""请仔细识别这张医学图片(处方/检查报告)中的所有文字,按原样输出。
要求:
1. **完整** —— 不要漏掉任何文字、数字、单位
2. **保留原始格式** —— 表格用 | 或空格分隔,列表用换行
3. **保留异常标记** —— ↑ ↓ 等
4. **如有多个区块**(如患者信息 + 项目列表 + 医嘱),用空行分隔

只输出 OCR 文本本身,不要加任何解释。"""

            # 在独立线程里跑 asyncio.run,绕开 uvicorn 的 uvloop
            import asyncio
            import threading

            result_holder = {"resp": None, "error": None}

            def _call():
                try:
                    client = AsyncOpenAI(
                        api_key=settings.OPENAI_API_KEY or "ollama",
                        base_url=settings.OPENAI_BASE_URL,
                        timeout=120.0,
                    )
                    result_holder["resp"] = asyncio.run(client.chat.completions.create(
                        model=model,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": data_url}}
                            ]
                        }],
                        temperature=0.1,
                        max_tokens=2000,
                    ))
                except Exception as e:
                    result_holder["error"] = e

            t = threading.Thread(target=_call, daemon=True)
            t.start()
            t.join(timeout=180)

            if result_holder["error"]:
                raise result_holder["error"]
            if result_holder["resp"] is None:
                raise TimeoutError("vision 识别超时(180s)")

            text = (result_holder["resp"].choices[0].message.content or "").strip()
            return {
                "engine": f"vision:{model}",
                "raw_text": text,
                "confidence": 0.92,
            }
        except Exception as e:
            logger.error(f"[OCR] vision 识别失败: {e},降级 mock")
            return self._recognize_mock(file_path, image_type_hint)

    def _recognize_tesseract(self, file_path: str, image_type_hint: str) -> Dict[str, Any]:
        try:
            from PIL import Image
            import pytesseract

            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            return {
                "engine": "tesseract",
                "raw_text": text.strip(),
                "confidence": 0.85,
            }
        except Exception as e:
            logger.error(f"[OCR] tesseract 识别失败: {e},降级 mock")
            return self._recognize_mock(file_path, image_type_hint)

    def _recognize_mock(self, file_path: str, image_type_hint: str) -> Dict[str, Any]:
        """Mock OCR - 仅用于演示(返回预设文本)"""
        file_hash = hashlib.md5(Path(file_path).read_bytes()).hexdigest()[:6]
        presets = {
            "prescription": """\
北京大学第三医院
电子处方笺
─────────────────────────────────
姓名:张三              性别:男    年龄:35岁
科室:心血管内科        门诊号:OP20260602001
日期:2026-06-02        医生:王医生

【临床诊断】
1. 高血压病(2 级)
2. 高脂血症

【Rp】
1. 苯磺酸氨氯地平片    5mg × 7 片
   用法:5mg 每日 1 次 口服
2. 阿托伐他汀钙片      20mg × 7 片
   用法:20mg 每日 1 次 睡前口服
3. 阿司匹林肠溶片      100mg × 30 片
   用法:100mg 每日 1 次 口服

【医嘱】低盐低脂饮食,每日测量血压。
医生签名:王医生""",
            "report": """\
北京大学第三医院
临床检验报告单
─────────────────────────────────
姓名:李四    性别:女  年龄:42岁
科室:内分泌科  病历号:M20260600012
送检日期:2026-06-01  报告日期:2026-06-02

【生化检验】项目    结果    参考值      单位
空腹血糖    7.2 ↑    3.9-6.1     mmol/L
糖化血红蛋白 8.5 ↑   4.0-6.0     %
总胆固醇    5.8 ↑    < 5.2       mmol/L
甘油三酯    2.3 ↑    < 1.7       mmol/L
尿酸        420 ↑    150-360    μmol/L

检验医师:张医生""",
        }
        if image_type_hint in presets:
            text = presets[image_type_hint]
        else:
            text = presets["prescription"] if int(file_hash, 16) % 2 == 0 else presets["report"]
        return {"engine": "mock", "raw_text": text, "confidence": 0.75}

    def save_upload(self, file_content: bytes, file_name: str) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file_name)
        target = UPLOAD_DIR / f"{ts}_{safe_name}"
        target.write_bytes(file_content)
        return str(target)


_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
