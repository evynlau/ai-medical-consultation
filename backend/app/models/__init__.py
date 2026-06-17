"""模型包"""
from app.models.user import User
from app.models.consultation import Consultation
from app.models.message import Message
from app.models.knowledge import Knowledge
from app.models.ocr import OcrRecord
from app.models.doctor import Doctor

__all__ = ["User", "Consultation", "Message", "Knowledge", "OcrRecord", "Doctor"]
