"""应用配置"""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "AI 智能问诊系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/medical.db"
    REDIS_URL: Optional[str] = None

    SECRET_KEY: str = "please-change-this-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # OCR 配置
    # engine: tesseract(本地 tesseract) | vision(多模态 LLM) | mock(演示文本)
    OCR_ENGINE: str = "auto"  # auto = 按可用性自动选 vision > tesseract > mock
    OCR_VISION_MODEL: str = ""  # 留空跟随 LLM 的 OPENAI_MODEL,或单独指定如 llama3.2-vision

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.2

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # 客户端超时(秒),给 LLM 充分思考时间
    API_RESPONSE_TIMEOUT: int = 180

    # 影像分析配置
    PNEUMONIA_MODEL_PATH: str = "./checkpoints/pneumonia_resnet50.pth"
    IMAGING_MAX_FILE_SIZE_MB: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
