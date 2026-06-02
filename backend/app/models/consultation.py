"""问诊会话模型"""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message


class Consultation(Base):
    """一次问诊会话"""

    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )  # 允许匿名问诊

    chief_complaint: Mapped[str] = mapped_column(String(500), nullable=False)  # 主诉
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/closed

    # Agent 输出的结构化诊断
    urgency_level: Mapped[int | None] = mapped_column(Integer, default=None)  # 1-4
    diagnosis_summary: Mapped[str | None] = mapped_column(Text, default=None)
    recommended_department: Mapped[str | None] = mapped_column(String(100), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User | None"] = relationship("User", back_populates="consultations")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="consultation", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
