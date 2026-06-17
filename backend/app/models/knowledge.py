"""医学知识库模型"""
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from typing import Any

from app.core.database import Base


class Knowledge(Base):
    """医学知识条目"""

    __tablename__ = "knowledge"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)  # disease/drug/examination/guideline
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str | None] = mapped_column(String(500), default=None)  # 逗号分隔
    source: Mapped[str | None] = mapped_column(String(255), default=None)  # 来源文档名
    extra: Mapped[Any | None] = mapped_column(JSON, default=None)  # 额外元数据(科室/症状等)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
