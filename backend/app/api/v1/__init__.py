"""API v1 路由汇总"""
from fastapi import APIRouter

from app.api.v1 import user, consult, agent, knowledge, admin, ocr, imaging, doctors

api_router = APIRouter()
api_router.include_router(user.router, prefix="/user", tags=["用户"])
api_router.include_router(consult.router, prefix="/consult", tags=["问诊"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理后台"])
api_router.include_router(ocr.router, prefix="/ocr", tags=["OCR 识别"])
api_router.include_router(imaging.router, prefix="/imaging", tags=["影像分析"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["名医录"])
