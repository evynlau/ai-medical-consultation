"""名医录模型"""
from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from app.core.database import Base


class Doctor(Base):
    """医生信息

    字段设计:
    - 核心字段(高频检索/展示):独立列 + 索引
    - 扩展字段(详细地址/出诊/学术成果):JSON 存 extra,避免一开始过度设计
    """

    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ===== 核心信息 =====
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # 科室
    hospital: Mapped[str] = mapped_column(String(200), nullable=False, index=True)    # 医院
    title: Mapped[str | None] = mapped_column(String(100), default=None)            # 主任医师/教授等
    diseases: Mapped[str | None] = mapped_column(String(500), default=None, index=True)  # 擅长疾病,逗号分隔
    city: Mapped[str | None] = mapped_column(String(50), default=None, index=True)   # 所在城市,便于按地区筛选
    avatar: Mapped[str | None] = mapped_column(String(500), default=None)
    bio: Mapped[str | None] = mapped_column(Text, default=None)                      # 简介(用于 RAG 检索)

    # ===== 扩展信息 =====
    # 详细地址 / 出诊信息 / 学术成果 等灵活字段统一放这里
    # 例:{"address":"xx路xx号","schedule":"周一上午","registration":"微医app","achievements":"SCI 30篇"}
    extra: Mapped[Any | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_doctor_dept_hospital", "department", "hospital"),
    )
