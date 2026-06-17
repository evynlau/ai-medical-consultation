"""初始化知识库:把 knowledge_base/ 下的 Markdown 灌入数据库 + 构建向量索引"""
import asyncio
import os
import sys
from pathlib import Path

# 把 backend 加入路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# 切到 backend 目录,这样 pydantic-settings 能找到 backend/.env
# (SettingsConfigDict(env_file=".env") 是相对 cwd 的;不切会读到错误的 .env 或漏读)
os.chdir(ROOT / "backend")

from app.core.database import init_db, AsyncSessionLocal
from app.models.knowledge import Knowledge
from app.services.rag_service import get_rag_service
from app.utils.logger import logger

# 类别映射:目录名 -> category 字段
CATEGORY_MAP = {
    "diseases": "disease",
    "drugs": "drug",
    "examinations": "examination",
    "guidelines": "guideline",
}


def parse_markdown(filepath: Path) -> dict:
    """解析单条 MD:第一个 # 作为 title,其余作为 content"""
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")
    title = filepath.stem
    content_lines = []
    tags = []

    for line in lines:
        if line.startswith("# ") and title == filepath.stem:
            title = line[2:].strip()
        elif line.startswith("## "):
            # 二级标题作为段落分隔
            content_lines.append("\n### " + line[3:].strip() + "\n")
        elif line.startswith("- "):
            content_lines.append(line)
            # 把列表项的关键词也作为 tag 候选
            word = line[2:].strip().split(" ")[0]
            if 1 < len(word) < 12:
                tags.append(word)
        elif line.strip():
            content_lines.append(line)

    return {
        "title": title,
        "content": "\n".join(content_lines).strip(),
        "tags": ",".join(tags[:10]),
    }


async def main():
    logger.info("🚀 初始化知识库...")
    await init_db()

    kb_root = ROOT / "knowledge_base"
    documents = []

    async with AsyncSessionLocal() as db:
        for dir_name, category in CATEGORY_MAP.items():
            sub = kb_root / dir_name
            if not sub.exists():
                continue
            for md_file in sub.glob("*.md"):
                parsed = parse_markdown(md_file)
                # 检查是否已存在
                from sqlalchemy import select
                stmt = select(Knowledge).where(
                    Knowledge.title == parsed["title"],
                    Knowledge.category == category,
                )
                exist = (await db.execute(stmt)).scalar_one_or_none()
                if exist:
                    logger.info(f"  · 跳过已存在: {parsed['title']}")
                    continue

                kb = Knowledge(
                    title=parsed["title"],
                    category=category,
                    content=parsed["content"],
                    tags=parsed["tags"],
                    source=str(md_file.relative_to(ROOT)),
                )
                db.add(kb)
                await db.flush()
                documents.append({
                    "id": kb.id,
                    "title": kb.title,
                    "content": kb.content,
                    "category": kb.category,
                    "tags": kb.tags or "",
                    "source": kb.source or "",
                })
                logger.info(f"  ✓ 已添加: [{category}] {parsed['title']}")

        await db.commit()

    # 构建索引(全量重建,避免只对新增条目索引导致漏检已存在但被外部修改的内容)
    logger.info("构建向量索引(全量,从数据库读取)...")
    async with AsyncSessionLocal() as db:
        all_rows = (await db.execute(select(Knowledge))).scalars().all()
        all_docs = [
            {
                "id": r.id, "title": r.title, "content": r.content,
                "category": r.category, "tags": r.tags or "", "source": r.source or "",
            }
            for r in all_rows
        ]
    if all_docs:
        rag = get_rag_service()
        rag.build_index(all_docs)
    else:
        logger.info("数据库为空,跳过索引构建")

    logger.info("✅ 知识库初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
