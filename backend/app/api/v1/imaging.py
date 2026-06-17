"""/api/v1/imaging - torchxrayvision 多分类胸片分析接口

按 xrv 官方范式:
  POST /pneumonia/analyze  - 上传胸片,返回 11 维多分类结果 + Grad-CAM
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.user import User
from app.models.imaging import ImagingAnalysis, DoctorAnnotation
from app.api.deps import get_doctor_user, get_admin_user, get_current_user
from app.services.imaging import get_xrv_service
from app.services.imaging.validation import validate_chest_xray
from app.utils.logger import logger
from app.core.config import settings

router = APIRouter()


# ====================== 响应模型 ======================

class AnnotationRequest(BaseModel):
    """医生标注请求"""
    annotation: str = Field(..., min_length=1, max_length=2000, description="标注说明")
    agreement: bool = Field(..., description="是否同意 AI 判断")
    correct_label: Optional[str] = Field(None, description="修正后的标签 (任意 pathology 英文名)")


class ImagingAnalysisOut(BaseModel):
    """影像分析响应 (兼容新旧字段)"""
    id: int
    image_filename: Optional[str]
    # 兼容旧字段 (数据库 ORM)
    prediction: Optional[str] = None
    prediction_label: Optional[str] = None
    probabilities: Optional[dict] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    inference_time_ms: Optional[int] = None
    gradcam: Optional[str] = None
    patient_id: Optional[int] = None
    consultation_id: Optional[int] = None
    doctor_id: Optional[int] = None
    annotation: Optional[str] = None
    doctor_agreement: Optional[bool] = None
    correct_label: Optional[str] = None
    created_at: Optional[datetime] = None
    # 新增字段 (xrv 官方范式)
    diagnosis: Optional[str] = None
    diagnosis_cn: Optional[str] = None
    positive_count: Optional[int] = None
    pathologies: Optional[list] = None
    model_name: Optional[str] = None

    class Config:
        from_attributes = True
        # 允许 ORM 字段名(下划线) 映射到 Pydantic 字段
        populate_by_name = True


# ====================== 接口 ======================

@router.post("/pneumonia/analyze")
async def analyze_pneumonia(
    file: UploadFile = File(..., description="影像文件 (JPEG/PNG)"),
    patient_id: Optional[int] = Form(None),
    consultation_id: Optional[int] = Form(None),
    include_gradcam: bool = Form(True),
    target_classes: str = Form("", description="要生成热力图的病理,逗号分隔,留空=所有阳性+肺炎"),
    apply_lung_mask: bool = Form(True, description="是否用 PSPNet 限制热力图到双肺内"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),  # 改为 get_current_user(登录用户即可)
):
    """torchxrayvision 多分类胸片分析

    返回:
      - diagnosis: 主诊断 (阳性概率/阈值比最高的病理, 或 "NORMAL")
      - pathologies: 11 维多分类结果 (每个含 prob/threshold/positive)
      - gradcams: 每个 target_class 一张 Grad-CAM (HiResCAM, 经 PSPNet 限制)
    """
    if file.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
        raise HTTPException(400, "仅支持 JPEG/PNG 格式")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件过大,最大支持 10MB")

    # 解析 target_classes
    requested = [c.strip() for c in target_classes.split(",") if c.strip()] or None

    # 验证上传图片是否为胸片(PSPNet 肺部分割法,完全本地、不依赖视觉 LLM)
    if settings.IMAGING_VALIDATION.lower() in ("true", "1", "on", "auto"):
        try:
            service = get_xrv_service()
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(contents))
            lung_mask = service._segment_lungs(img)
            if lung_mask is None:
                # PSPNet 不可用(模型未加载),跳过
                validation = {
                    "skipped": True, "is_chest_xray": True, "confidence": 0.0,
                    "reason": "PSPNet unavailable", "view": "unknown", "engine": "pspnet",
                }
            else:
                # 算双肺区域占比
                lung_ratio = float(lung_mask.sum()) / float(lung_mask.size)
                MIN_LUNG_RATIO = 0.005  # 0.5% (真胸片通常 8-25%)
                is_cxr = lung_ratio >= MIN_LUNG_RATIO
                validation = {
                    "skipped": False,
                    "is_chest_xray": bool(is_cxr),
                    "confidence": min(1.0, max(0.0, lung_ratio * 10)),
                    "reason": f"PSPNet 肺野占比 {lung_ratio*100:.2f}%" + ("" if is_cxr else " (低于阈值 0.5%,可能不是胸片)"),
                    "view": "unknown",
                    "engine": "pspnet",
                }
                if not is_cxr:
                    raise HTTPException(
                        422,
                        f"上传图片可能不是胸片:PSPNet 未能识别到双肺区域(肺野占比仅 {lung_ratio*100:.2f}%,正常胸片通常 8-25%)。请上传胸片 X-ray。",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[ImagingValidation] PSPNet 验证失败,放行: {e}")
            validation = {
                "skipped": True, "is_chest_xray": True, "confidence": 0.0,
                "reason": f"validation error: {e}", "view": "unknown", "engine": "error",
            }
    else:
        validation = {
            "skipped": True, "is_chest_xray": True, "confidence": 0.0,
            "reason": "validation disabled", "view": "unknown", "engine": "none",
        }

    try:
        service = get_xrv_service()
        if include_gradcam:
            result = service.predict_from_bytes_with_gradcam(
                contents, target_classes=requested, apply_lung_mask=apply_lung_mask
            )
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
        prediction=result["diagnosis"],
        prediction_label=result["diagnosis_cn"],
        probabilities={"confidence": result["confidence"], "positive_count": result["positive_count"]},
        confidence=result["confidence"],
        model_version=result["model_weights"],
        inference_time_ms=result["inference_time_ms"],
        gradcam=result["gradcams"][0]["overlay"] if result.get("gradcams") else None,
        patient_id=patient_id,
        consultation_id=consultation_id,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return {
        "id": analysis.id,
        "image_filename": file.filename,
        "diagnosis": result["diagnosis"],
        "diagnosis_cn": result["diagnosis_cn"],
        "confidence": result["confidence"],
        "positive_count": result["positive_count"],
        "pathologies": result["pathologies"],
        "model_name": result["model_name"],
        "model_weights": result["model_weights"],
        "inference_time_ms": result["inference_time_ms"],
        "gradcams": result.get("gradcams", []),
        "original_image": result.get("original_image"),
        "original_image_size": result.get("original_image_size"),
        "lung_mask_applied": result.get("lung_mask_applied", False),
        "threshold_source": result.get("threshold_source", "xrv 官方"),
        "target_classes": requested or [],
        "validation": validation,  # 胸片内容验证结果(view/confidence/reason/engine)
        "warnings": [
            "本结果仅供医生参考,不作为最终诊断依据",
            "请结合临床症状和其他检查综合判断",
        ],
        "disclaimer": "AI 辅助诊断工具,最终诊断需由专业医生确认",
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

    if user.is_doctor:
        stmt = stmt.where(ImagingAnalysis.user_id == user.id)
    elif not user.is_admin:
        stmt = stmt.where(ImagingAnalysis.user_id == user.id)

    if patient_id:
        stmt = stmt.where(ImagingAnalysis.patient_id == patient_id)
    if doctor_id:
        stmt = stmt.where(ImagingAnalysis.user_id == doctor_id)

    stmt = stmt.order_by(desc(ImagingAnalysis.created_at)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    # 字段映射: ORM -> API (兼容旧 prediction / 新 diagnosis)
    return [_to_api_dict(r) for r in rows]


@router.get("/{analysis_id}", response_model=ImagingAnalysisOut)
async def get_analysis_detail(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    analysis = await db.get(ImagingAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(404, "分析记录不存在")
    if not user.is_admin and analysis.user_id != user.id:
        raise HTTPException(403, "无权查看")
    return _to_api_dict(analysis)


def _to_api_dict(row) -> dict:
    """ORM ImagingAnalysis -> API 响应 dict (兼容新旧字段)"""
    import json
    probs_dict = row.probabilities or {}
    # probabilities 字段在 analyze 时存的是 {"NORMAL": ..., "PNEUMONIA": ...} 或 {"confidence": ..., "positive_count": ...}
    if "NORMAL" in probs_dict:
        # 旧格式
        api_probs = probs_dict
    else:
        # 新格式
        api_probs = probs_dict
    return {
        "id": row.id,
        "image_filename": row.image_filename,
        # 旧字段 (兼容)
        "prediction": row.prediction,
        "prediction_label": row.prediction_label,
        "probabilities": api_probs,
        "confidence": row.confidence,
        "model_version": row.model_version,
        "inference_time_ms": row.inference_time_ms,
        "gradcam": row.gradcam,
        "patient_id": row.patient_id,
        "consultation_id": row.consultation_id,
        "doctor_id": row.user_id,
        "annotation": row.annotation,
        "doctor_agreement": row.doctor_agreement,
        "correct_label": row.correct_label,
        "created_at": row.created_at,
        # 新字段 (xrv 官方范式, 从 ORM 推导)
        "diagnosis": row.prediction,
        "diagnosis_cn": row.prediction_label,
        "positive_count": probs_dict.get("positive_count"),
        "pathologies": None,  # 历史记录不存 18 维, 只存主诊断
        "model_name": row.model_version,
    }


@router.post("/{analysis_id}/annotate")
async def submit_annotation(
    analysis_id: int,
    payload: AnnotationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_doctor_user),
):
    analysis = await db.get(ImagingAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(404, "分析记录不存在")

    annotation = DoctorAnnotation(
        analysis_id=analysis_id,
        doctor_id=user.id,
        annotation=payload.annotation,
        agreement=payload.agreement,
        correct_label=payload.correct_label,
    )
    db.add(annotation)
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
async def list_available_models(user: User = Depends(get_admin_user)):
    """列出可用模型 (管理员)"""
    service = get_xrv_service()
    return {
        "models": [
            {
                "name": str(service._xrv_model),
                "weights": "densenet121-res224-chex",
                "pathologies": [p for p in service._xrv_model.pathologies if p],
                "calibrated": False,  # 完全用 xrv 官方 op_threshs, 不做自校准
                "is_loaded": service._xrv_model is not None,
            }
        ]
    }
