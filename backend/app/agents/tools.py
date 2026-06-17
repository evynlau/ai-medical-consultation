"""LangChain Tool 包装层

将既有服务 (OCR / 医学影像) 包成 LangChain BaseTool,供 LangGraph
bind_tools() + ToolNode 调用。

设计要点:
    1. **同步包装**:OCR / 影像服务都是同步方法,BaseTool 默认 invoke 同步;
       ToolNode 会用 asyncio.to_thread 包装(由 LangGraph 处理)。
    2. **降级友好**:调失败时返回结构化错误信息(不抛异常),让 LLM 可以继续决策。
    3. **不重写** OCR / 影像服务 — 只是适配层,业务逻辑 0 重复。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.ocr_service import get_ocr_service
from app.utils.logger import logger


# ====================== Tool 1: OCR 识别 ======================

class OCRInput(BaseModel):
    file_path: str = Field(..., description="待识别的图片绝对路径(处方/检查报告等)")
    image_type_hint: str = Field(
        default="", description="可选提示,如 'prescription'(处方) / 'lab_report'(化验单)"
    )


class OCROCRTool(BaseTool):
    name: str = "ocr_recognize"
    description: str = (
        "用 OCR 识别医学图片(处方/检查报告/化验单)中的文字。"
        "当用户提到 '这份报告' / '这个处方' / '化验单' / '我上传了图片' "
        "或显式提供了 image_path 时,必须调用此工具。"
        "返回识别出的原始文本,供后续问诊分析使用。"
    )
    args_schema: Type[BaseModel] = OCRInput

    def _run(
        self,
        file_path: str,
        image_type_hint: str = "",
        run_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not file_path or not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"图片路径不存在: {file_path}",
                "raw_text": "",
            }
        try:
            ocr = get_ocr_service()
            result = ocr.recognize(file_path, image_type_hint=image_type_hint)
            return {
                "success": True,
                "engine": result.get("engine", "unknown"),
                "raw_text": result.get("raw_text", ""),
                "confidence": result.get("confidence", 0.0),
            }
        except Exception as e:
            logger.exception(f"[OCRTool] 识别失败: {e}")
            return {"success": False, "error": str(e), "raw_text": ""}

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 同步工具包一层异步,ToolNode 会用 to_thread 跑
        import asyncio
        return await asyncio.to_thread(self._run, **kwargs)


# ====================== Tool 2: 医学影像分析 ======================

class ImagingInput(BaseModel):
    file_path: str = Field(..., description="胸片图片的绝对路径")
    generate_gradcam: bool = Field(
        default=True, description="是否生成 Grad-CAM 热力图(用于解释模型关注点)"
    )


class ImagingAnalysisTool(BaseTool):
    name: str = "chest_xray_analyze"
    description: str = (
        "用胸片专用模型 (xrv DenseNet121) 分析用户上传的胸片,返回肺炎概率、"
        "Top-K 病理标签和 Grad-CAM 热力图 base64。"
        "当用户说 '我拍了胸片' / '看看这张 X 光' / 'CT 结果' 或提供 image_path 时调用。"
        "返回结构化结果含 pneumonia_prob / top_labels[] / gradcam_b64。"
    )
    args_schema: Type[BaseModel] = ImagingInput

    def _run(
        self,
        file_path: str,
        generate_gradcam: bool = True,
        run_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": f"图片路径不存在: {file_path}"}
        try:
            with open(file_path, "rb") as f:
                image_bytes = f.read()
            from app.services.imaging.xrv_service import get_xrv_service
            svc = get_xrv_service()
            if generate_gradcam:
                # 带 Grad-CAM(返回热力图 base64)
                result = svc.predict_from_bytes_with_gradcam(
                    image_bytes,
                    apply_lung_mask=True,
                )
            else:
                result = svc.predict_from_bytes(image_bytes)
            return {"success": True, **result}
        except Exception as e:
            logger.exception(f"[ImagingTool] 分析失败: {e}")
            return {"success": False, "error": str(e)}

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        import asyncio
        return await asyncio.to_thread(self._run, **kwargs)


# ====================== 工厂 ======================

OCR_TOOL = OCROCRTool()
IMAGING_TOOL = ImagingAnalysisTool()
ALL_TOOLS = [OCR_TOOL, IMAGING_TOOL]


def get_tools():
    return ALL_TOOLS


def decide_tools_for_state(image_path: Optional[str] = None) -> list:
    """mock 模式下的"伪决策":根据 image_path 是否存在选工具

    真 LLM 模式走 bind_tools() + ToolNode 让 LLM 自己决策;
    mock 模式 / 失败降级走这里。

    启发式(没有真视觉能力):
        - 文件名含 'prescription' / '处方' / 'report' / '报告' / '化验' → OCR
        - 文件名含 'xray' / 'ct' / 'x光' / '胸片' / 'lung' → 影像
        - 默认 → 影像(医学场景以胸片为主)
    """
    if not image_path:
        return []
    name = os.path.basename(image_path).lower()
    if any(k in name for k in ("prescription", "处方", "report", "报告", "化验", "lab")):
        return [OCR_TOOL]
    # 默认走影像(胸片)
    return [IMAGING_TOOL]
