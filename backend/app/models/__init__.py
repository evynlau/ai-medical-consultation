"""模型包"""
from app.models.user import User
from app.models.consultation import Consultation
from app.models.message import Message
from app.models.knowledge import Knowledge

__all__ = ["User", "Consultation", "Message", "Knowledge"]
