"""医学影像分析记录模型"""
from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImagingAnalysis(Base):
    """影像分析记录"""

    __tablename__ = "imaging_analysis"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 上传医生
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # 关联 (可选)
    patient_id: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    consultation_id: Mapped[int | None] = mapped_column(Integer, default=None, index=True)

    # 影像信息
    image_filename: Mapped[str | None] = mapped_column(String(255), default=None)
    image_size: Mapped[str | None] = mapped_column(String(50), default=None)  # "W,H"

    # AI 预测
    prediction: Mapped[str] = mapped_column(String(50), index=True)  # NORMAL/PNEUMONIA
    prediction_label: Mapped[str] = mapped_column(String(100))  # 中文标签
    probabilities: Mapped[Any] = mapped_column(JSON)  # {NORMAL: 0.x, PNEUMONIA: 0.x}
    confidence: Mapped[float] = mapped_column(default=0.0)
    model_version: Mapped[str] = mapped_column(String(50), default="resnet50_v1.0")
    inference_time_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    # Grad-CAM (Base64)
    gradcam: Mapped[str | None] = mapped_column(Text, default=None)

    # 医生标注
    annotation: Mapped[str | None] = mapped_column(Text, default=None)
    doctor_agreement: Mapped[bool | None] = mapped_column(Boolean, default=None)
    correct_label: Mapped[str | None] = mapped_column(String(50), default=None)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DoctorAnnotation(Base):
    """医生标注记录"""

    __tablename__ = "doctor_annotation"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 关联
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("imaging_analysis.id"), index=True
    )
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # 标注内容
    annotation: Mapped[str] = mapped_column(Text)  # 标注说明
    agreement: Mapped[bool] = mapped_column(Boolean)  # 是否同意 AI 判断
    correct_label: Mapped[str | None] = mapped_column(String(50), default=None)  # 修正后标签

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImagingModel(Base):
    """模型管理 (用于多模态扩展)"""

    __tablename__ = "imaging_model"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # e.g., pneumonia_resnet50
    modality: Mapped[str] = mapped_column(String(50), index=True)  # X-ray/CT/MRI/Ultrasound
    task: Mapped[str] = mapped_column(String(100))  # 二分类/检测/分割
    version: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(500))
    classes: Mapped[Any] = mapped_column(JSON)  # 类别列表

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)