"""OCR 记录模型"""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from typing import Any, Optional

from app.core.database import Base


class OcrRecord(Base):
    """OCR 识别记录(处方 / 检查报告)"""
    __tablename__ = "ocr_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )

    # 类型:image_type = prescription(处方) | report(检查报告) | other
    image_type: Mapped[str] = mapped_column(String(20), default="other", index=True)

    # 文件信息
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)  # 字节
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # 保存路径

    # OCR 引擎:tesseract | mock
    ocr_engine: Mapped[str] = mapped_column(String(20), default="mock")

    # 原始 OCR 文本
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # LLM 结构化结果(JSON)
    structured_data: Mapped[Optional[Any]] = mapped_column(JSON, default=None)

    # 识别置信度(0-1)
    confidence: Mapped[float] = mapped_column(default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
