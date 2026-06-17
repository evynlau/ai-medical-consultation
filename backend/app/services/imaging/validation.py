"""影像上传前内容验证 - 用多模态 LLM 判断上传图是否为胸片 X-ray
- 避免「随便传张图就分析」造成的无意义 AI 输出
- 复用现有 vision LLM 配置(与 OCR 共享)
- 失败优雅降级,默认不阻塞(mock 模式下 LLM 不可用时直接放行)
"""
import base64
import mimetypes
import asyncio
import threading
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.utils.logger import logger


# 验证 prompt - 让 LLM 二分类并解释
_VALIDATION_PROMPT = """请判断这张图片是否是**胸部 X 光片(chest X-ray / CXR / 胸片)**。

判断标准:
- ✅ 胸片:PA 位 / AP 位 / 侧位 胸片,可见双肺野、心影、肋骨、纵隔
- ✅ 胸片相关:CT 胸片(胸部 CT 单层)、报告中的胸片缩略图
- ❌ 非胸片:CT/MRI 其他部位、照片、风景、报告单、处方、其他 X 光(牙片、骨片、关节等)

请严格按以下 JSON 格式回答,只输出 JSON,不要其他文字:
{{
  "is_chest_xray": true 或 false,
  "confidence": 0.0 到 1.0 之间的数字,
  "reason": "简短的判断理由(15 字以内)",
  "view": "PA / AP / LAT / CT / unknown"
}}"""


def _should_validate() -> bool:
    """是否启用验证。
    - 显式 "true"/"false" 强制
    - "auto" 仅在有真实 vision LLM 时启用
    """
    mode = (settings.IMAGING_VALIDATION or "auto").lower()
    if mode == "false" or mode == "0" or mode == "off":
        return False
    if mode == "true" or mode == "1" or mode == "on":
        return True
    # auto: 仅有真实 LLM 时启用
    if settings.LLM_PROVIDER == "mock":
        return False
    has_key = bool(settings.OPENAI_API_KEY) and settings.OPENAI_API_KEY not in ("", "your-openai-api-key", "ollama")
    has_url = bool(settings.OPENAI_BASE_URL) and settings.OPENAI_BASE_URL != "https://api.openai.com/v1"
    return has_key or has_url


def _pick_model() -> Optional[str]:
    """选择用于验证的视觉模型"""
    return (
        settings.IMAGING_VALIDATION_MODEL
        or settings.OCR_VISION_MODEL
        or settings.OPENAI_MODEL
    )


def _image_to_data_url(image_bytes: bytes, filename: str = "upload.png") -> str:
    """把图片字节编码为 LLM 可识别的 data URL"""
    # 根据文件后缀猜 mime
    suffix = Path(filename).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    mime = mime_map.get(suffix, "image/jpeg")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _parse_validation_response(text: str) -> Optional[dict]:
    """从 LLM 响应中提取 JSON"""
    import json
    import re

    if not text:
        return None
    text = text.strip()

    # 尝试直接 parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 尝试从 markdown 代码块提取
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 尝试提取第一个 { ... } 块
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    return None


def validate_chest_xray(image_bytes: bytes, filename: str = "upload.png", timeout: float = 30.0) -> dict:
    """验证上传图片是否为胸片 X-ray

    Returns:
        {
            "skipped": bool,          # 是否跳过(未启用验证或 LLM 不可用)
            "is_chest_xray": bool,    # 是否胸片(只有未 skipped 时才有意义)
            "confidence": float,       # LLM 置信度
            "reason": str,             # 拒绝/通过的理由
            "view": str,               # PA/AP/LAT/CT/unknown
            "engine": str,             # 验证引擎
        }

    失败/超时/解析失败 → 放行(skipped=True, is_chest_xray=True, reason=具体原因)
    严格启用时,可在调用方根据 is_chest_xray=False 拒绝。
    """
    if not _should_validate():
        return {
            "skipped": True,
            "is_chest_xray": True,
            "confidence": 0.0,
            "reason": "validation disabled or no vision LLM",
            "view": "unknown",
            "engine": "none",
        }

    model = _pick_model()
    if not model:
        logger.warning("[ImagingValidation] 未配置视觉模型,跳过")
        return {
            "skipped": True,
            "is_chest_xray": True,
            "confidence": 0.0,
            "reason": "no vision model configured",
            "view": "unknown",
            "engine": "none",
        }

    try:
        from openai import AsyncOpenAI
        from app.services.llm_service import build_thinking_disable_kwargs

        data_url = _image_to_data_url(image_bytes, filename)
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "ollama",
            base_url=settings.OPENAI_BASE_URL,
            timeout=60.0,
        )

        # 注入 thinking-disable 参数(避免 LLM 在 verify 任务中输出 reasoning)
        extra_kwargs = build_thinking_disable_kwargs(
            model_name=model, base_url=settings.OPENAI_BASE_URL, force_disable=True,
        )

        result_holder = {"resp": None, "error": None}

        def _call():
            try:
                result_holder["resp"] = asyncio.run(client.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _VALIDATION_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }],
                    temperature=0.0,
                    max_tokens=300,
                    **extra_kwargs,
                ))
            except Exception as e:
                result_holder["error"] = e

        t = threading.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if result_holder["error"]:
            raise result_holder["error"]
        if result_holder["resp"] is None:
            raise TimeoutError(f"vision validation timeout ({timeout}s)")

        text = (result_holder["resp"].choices[0].message.content or "").strip()
        logger.info(f"[ImagingValidation] model={model} resp={text[:120]}")

        parsed = _parse_validation_response(text)
        if not parsed:
            logger.warning(f"[ImagingValidation] 解析失败: {text[:200]}")
            return {
                "skipped": True,
                "is_chest_xray": True,
                "confidence": 0.0,
                "reason": "response parse failed - allowed",
                "view": "unknown",
                "engine": f"vision:{model}",
            }

        is_cxr = bool(parsed.get("is_chest_xray", False))
        conf = float(parsed.get("confidence", 0.0))
        reason = str(parsed.get("reason", ""))
        view = str(parsed.get("view", "unknown"))

        return {
            "skipped": False,
            "is_chest_xray": is_cxr,
            "confidence": conf,
            "reason": reason,
            "view": view,
            "engine": f"vision:{model}",
        }
    except Exception as e:
        # 失败放行,不阻塞
        logger.warning(f"[ImagingValidation] 失败,放行: {e}")
        return {
            "skipped": True,
            "is_chest_xray": True,
            "confidence": 0.0,
            "reason": f"validation error: {e}",
            "view": "unknown",
            "engine": "error",
        }
