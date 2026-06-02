"""用户模型"""
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.consultation import Consultation


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), default=None)

    # 患者画像
    age: Mapped[int | None] = mapped_column(default=None)
    gender: Mapped[str | None] = mapped_column(String(20), default=None)  # male/female/other
    allergies: Mapped[str | None] = mapped_column(String(500), default=None)  # 过敏史
    chronic_diseases: Mapped[str | None] = mapped_column(String(500), default=None)  # 慢性病

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # 管理员
    is_doctor: Mapped[bool] = mapped_column(Boolean, default=False)  # 医生(可回复)
    specialty: Mapped[str | None] = mapped_column(String(50), default=None)  # 医生科室
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    consultations: Mapped[List["Consultation"]] = relationship(
        "Consultation", back_populates="user", cascade="all, delete-orphan",
        lazy="selectin",
    )
