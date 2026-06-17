"""数据库连接 - SQLAlchemy 异步"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


# 兼容 SQLite:SQLite 异步引擎需要特殊参数
_engine_kwargs = {"echo": settings.DEBUG}
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖:获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库表 + 轻量级列迁移(新加的列)"""
    # 导入所有模型以确保注册到 Base.metadata
    from app.models import user, consultation, message, knowledge  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ===== 轻量迁移:为已存在的旧表加新列(无 Alembic 时的兼容方案) =====
    # Knowledge.updated_at(Knowledge 在最新版本里加了这一列,旧库要补)
    await _ensure_column("knowledge", "updated_at", "DATETIME")


async def _ensure_column(table: str, column: str, sql_type: str) -> None:
    """列不存在则 ALTER TABLE 添加(幂等,不会重复加)"""
    from sqlalchemy import text, inspect
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            # SQLite:PRAGMA 查列
            rows = await conn.execute(text(f"PRAGMA table_info({table})"))
            cols = {row[1] for row in rows}
        else:
            # MySQL / PostgreSQL:information_schema
            rows = await conn.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_NAME='{table}'"
            ))
            cols = {row[0] for row in rows}
        if column not in cols:
            await conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"
            ))
