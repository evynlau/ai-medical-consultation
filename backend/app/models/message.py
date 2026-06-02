"""问诊消息模型"""
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Any
from sqlalchemy import JSON

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.consultation import Consultation


class Message(Base):
    """问诊消息(用户/AI 均可)"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    consultation_id: Mapped[int] = mapped_column(
        ForeignKey("consultations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant / system / doctor
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # text/analysis/doctor_reply

    # 医生回复关联
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)

    # 引用知识来源(可选,JSON 数组)
    source_knowledge: Mapped[Any | None] = mapped_column(JSON, default=None)

    # 紧急程度(仅 assistant 分析消息)
    urgency_level: Mapped[int | None] = mapped_column(Integer, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    consultation: Mapped["Consultation"] = relationship("Consultation", back_populates="messages")
