"""模型包"""
from app.models.user import User
from app.models.consultation import Consultation
from app.models.message import Message
from app.models.knowledge import Knowledge
from app.models.ocr import OcrRecord

__all__ = ["User", "Consultation", "Message", "Knowledge", "OcrRecord"]
