"""FastAPI 应用入口"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import api_router
from app.api.ws.chat import websocket_endpoint
from app.core.lifespan import warmup_rag
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"   LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"   Embedding Provider: {settings.EMBEDDING_PROVIDER}")
    logger.info(f"   Database: {settings.DATABASE_URL}")
    logger.info("=" * 50)

    # 1. 初始化数据库
    try:
        await init_db()
        logger.info("✅ 数据库表已创建")
    except Exception as e:
        logger.exception(f"数据库初始化失败: {e}")

    # 2. 预热 RAG
    await warmup_rag()

    yield

    logger.info("👋 应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## AI 智能问诊系统

基于 LLM + Agent + RAG 的医疗问诊平台。

### 核心能力
- 🤖 智能症状分析(结构化 JSON 输出)
- 📚 医学知识库 RAG 检索
- 🏥 智能分诊(紧急程度 + 推荐科室)
- 💬 多轮对话问诊
- 🚨 紧急症状识别
- 💾 问诊历史持久化
""",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"] if settings.DEBUG else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(api_router, prefix="/api/v1")
app.add_api_websocket_route("/api/ws/chat", websocket_endpoint)


# ====================== 基础端点 ======================

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


# ====================== 前端静态托管(可选) ======================

# 如果构建了前端,可挂载到 /web 路径
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/web", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    logger.info(f"前端静态文件已挂载: {frontend_dist}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
