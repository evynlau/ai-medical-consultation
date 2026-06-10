"""/api/v1/imaging - 影像分析接口
医生辅助诊断模块
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.user import User
from app.models.imaging import ImagingAnalysis, DoctorAnnotation
from app.api.deps import get_doctor_user, get_admin_user, get_current_user
from app.services.imaging import get_pneumonia_service
from app.utils.logger import logger

router = APIRouter()


# ====================== 响应模型 ======================

class AnnotationRequest(BaseModel):
    """医生标注请求"""
    annotation: str = Field(..., min_length=1, max_length=2000, description="标注说明")
    agreement: bool = Field(..., description="是否同意 AI 判断")
    correct_label: Optional[str] = Field(None, description="修正后的标签 (PNEUMONIA/NORMAL)")


class ImagingAnalysisOut(BaseModel):
    """影像分析响应"""
    id: int
    image_filename: Optional[str]
    prediction: str
    prediction_label: str
    probabilities: dict
    confidence: float
    model_version: str
    inference_time_ms: Optional[int]
    gradcam: Optional[str]
    patient_id: Optional[int]
    consultation_id: Optional[int]
    doctor_id: Optional[int]
    annotation: Optional[str]
    doctor_agreement: Optional[bool]
    correct_label: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ====================== 接口 ======================

@router.post("/pneumonia/analyze")
async def analyze_pneumonia(
    file: UploadFile = File(..., description="影像文件 (JPEG/PNG)"),
    patient_id: Optional[int] = Form(None),
    consultation_id: Optional[int] = Form(None),
    include_gradcam: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_doctor_user),
):
    """上传胸片,AI辅助分析肺炎

    支持的影像类型: JPEG, PNG
    限制: 10MB
    """
    # 验证文件类型
    if file.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
        raise HTTPException(400, "仅支持 JPEG/PNG 格式")

    # 读取文件
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件过大,最大支持 10MB")

    # AI 推理
    try:
        service = get_pneumonia_service()
        if include_gradcam:
            result = service.predict_from_bytes_with_gradcam(contents)
        else:
            result = service.predict_from_bytes(contents)
    except Exception as e:
        logger.error(f"影像分析失败: {e}")
        raise HTTPException(500, f"AI 分析失败: {str(e)}")

    # 保存到数据库
    analysis = ImagingAnalysis(
        user_id=user.id,
        image_filename=file.filename,
        image_size=str(result.get("original_image_size", "")),
        prediction=result["prediction"],
        prediction_label=result["prediction_label"],
        probabilities=result["probabilities_dict"],
        confidence=result["confidence"],
        model_version=result["model_version"],
        inference_time_ms=result.get("inference_time_ms"),
        gradcam=result.get("gradcam"),
        patient_id=patient_id,
        consultation_id=consultation_id,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return {
        "id": analysis.id,
        "prediction": result["prediction"],
        "prediction_label": result["prediction_label"],
        "probabilities": result["probabilities_dict"],
        "confidence": result["confidence"],
        "model_version": result["model_version"],
        "inference_time_ms": result.get("inference_time_ms"),
        "gradcam": result.get("gradcam"),  # 已叠加的热力图(原图+热度)
        "gradcam_raw": result.get("gradcam_raw"),  # 仅热力图(透明PNG,用于前端叠加)
        "original_image": result.get("original_image"),  # 原始图像 base64
        "original_image_size": result.get("original_image_size"),
        "warnings": [
            "本结果仅供医生参考,不作为最终诊断依据",
            "请结合临床症状和其他检查综合判断",
        ],
        "disclaimer": "AI辅助诊断工具,最终诊断需由专业医生确认",
    }


@router.get("/history", response_model=List[ImagingAnalysisOut])
async def get_analysis_history(
    patient_id: Optional[int] = Query(None),
    doctor_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取分析历史记录"""
    stmt = select(ImagingAnalysis)

    # 权限控制
    if user.is_doctor:
        # 医生只看自己的
        stmt = stmt.where(ImagingAnalysis.user_id == user.id)
    elif not user.is_admin:
        # 其他用户只能看自己的
        stmt = stmt.where(ImagingAnalysis.user_id == user.id)

    if patient_id:
        stmt = stmt.where(ImagingAnalysis.patient_id == patient_id)
    if doctor_id:
        stmt = stmt.where(ImagingAnalysis.user_id == doctor_id)

    stmt = stmt.order_by(desc(ImagingAnalysis.created_at)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get("/{analysis_id}", response_model=ImagingAnalysisOut)
async def get_analysis_detail(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取单个分析详情"""
    analysis = await db.get(ImagingAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(404, "分析记录不存在")

    # 权限检查
    if not user.is_admin and analysis.user_id != user.id:
        raise HTTPException(403, "无权查看")

    return analysis


@router.post("/{analysis_id}/annotate")
async def submit_annotation(
    analysis_id: int,
    payload: AnnotationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_doctor_user),
):
    """医生提交标注"""
    analysis = await db.get(ImagingAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(404, "分析记录不存在")

    # 创建标注记录
    annotation = DoctorAnnotation(
        analysis_id=analysis_id,
        doctor_id=user.id,
        annotation=payload.annotation,
        agreement=payload.agreement,
        correct_label=payload.correct_label,
    )
    db.add(annotation)

    # 同时更新分析记录的标注字段
    analysis.annotation = payload.annotation
    analysis.doctor_agreement = payload.agreement
    analysis.correct_label = payload.correct_label

    await db.commit()
    await db.refresh(annotation)

    return {
        "success": True,
        "annotation_id": annotation.id,
        "message": "标注已保存",
    }


@router.get("/{analysis_id}/annotations")
async def list_annotations(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取标注列表"""
    stmt = (
        select(DoctorAnnotation)
        .where(DoctorAnnotation.analysis_id == analysis_id)
        .order_by(desc(DoctorAnnotation.created_at))
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": a.id,
            "doctor_id": a.doctor_id,
            "annotation": a.annotation,
            "agreement": a.agreement,
            "correct_label": a.correct_label,
            "created_at": a.created_at,
        }
        for a in rows
    ]


@router.get("/models/list")
async def list_available_models(
    user: User = Depends(get_admin_user),
):
    """列出可用模型 (管理员)"""
    service = get_pneumonia_service()
    return {
        "models": [
            {
                "name": "pneumonia_resnet50",
                "version": service.config.get("model_version", "unknown"),
                "classes": service.config.get("classes", []),
                "image_size": service.config.get("image_size", 224),
                "is_loaded": service.model is not None,
            }
        ]
    }