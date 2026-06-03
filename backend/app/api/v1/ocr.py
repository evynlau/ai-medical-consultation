"""/api/v1/ocr - 处方/检查报告 OCR
"""
import re
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.user import User
from app.models.ocr import OcrRecord
from app.api.deps import get_current_user_optional, get_current_user
from app.services.ocr_service import get_ocr_service
from app.services.llm_service import get_llm_service
from app.schemas.ocr import OcrUploadResponse, OcrRecordListItem, OcrRecordDetail
from app.utils.logger import logger

router = APIRouter()

# 允许的图片类型
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp", "image/bmp"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload", response_model=OcrUploadResponse)
async def upload_and_recognize(
    file: UploadFile = File(...),
    image_type: str = Form("auto", description="prescription | report | auto"),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """上传图片,识别后用 LLM 结构化"""
    # 校验
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"不支持的文件类型: {file.content_type}。请上传 JPG/PNG/WEBP/BMP")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, f"文件过大({len(content)//1024} KB),最大 10MB")

    # 1. 保存文件
    ocr_svc = get_ocr_service()
    file_path = ocr_svc.save_upload(content, file.filename or "upload.png")

    # 2. OCR 识别
    ocr_result = ocr_svc.recognize(file_path, image_type_hint=image_type)
    raw_text = ocr_result["raw_text"]
    confidence = ocr_result["confidence"]
    engine = ocr_result["engine"]

    # 3. 用 LLM 把 OCR 文本结构化
    structured = None
    try:
        llm = get_llm_service()
        structured = await _structure_with_llm(llm, raw_text, image_type)
    except Exception as e:
        logger.error(f"[OCR] LLM 结构化失败: {e}")

    # 4. 写库
    record = OcrRecord(
        user_id=user.id if user else None,
        image_type=image_type if image_type != "auto" else _guess_type(raw_text),
        file_name=file.filename or "upload.png",
        file_size=len(content),
        file_path=file_path,
        ocr_engine=engine,
        raw_text=raw_text,
        structured_data=structured,
        confidence=confidence,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    logger.info(f"[OCR] 识别完成: id={record.id}, engine={engine}, type={record.image_type}")

    return OcrUploadResponse(
        id=record.id,
        image_type=record.image_type,
        file_name=record.file_name,
        file_size=record.file_size,
        ocr_engine=record.ocr_engine,
        confidence=record.confidence,
        raw_text=record.raw_text,
        structured_data=record.structured_data,
        created_at=record.created_at,
    )


@router.get("/records", response_model=List[OcrRecordListItem])
async def list_records(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    image_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """我的 OCR 记录(必须登录)"""
    stmt = select(OcrRecord).where(OcrRecord.user_id == user.id)
    if image_type:
        stmt = stmt.where(OcrRecord.image_type == image_type)
    stmt = stmt.order_by(desc(OcrRecord.created_at)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get("/records/{record_id}", response_model=OcrRecordDetail)
async def get_record(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """OCR 记录详情"""
    rec = await db.get(OcrRecord, record_id)
    if not rec:
        raise HTTPException(404, "记录不存在")
    if rec.user_id and rec.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "无权访问")
    return rec


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    record_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rec = await db.get(OcrRecord, record_id)
    if not rec:
        raise HTTPException(404, "记录不存在")
    if rec.user_id and rec.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "无权访问")
    # 删文件
    try:
        Path(rec.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(rec)
    await db.commit()
    return None


# ============== 内部 ==============

async def _structure_with_llm(llm, raw_text: str, image_type: str) -> dict:
    """用 LLM 把 OCR 文本结构化"""
    prompt = f"""请把以下 OCR 识别出的医学文本结构化为 JSON。

【原始 OCR 文本】
{raw_text}

【输出要求 - 严格 JSON】
根据内容判断是"处方"还是"检查报告",并提取对应字段:

如果是处方(prescription),输出:
{{
  "document_type": "prescription",
  "patient": {{"name": "...", "gender": "...", "age": ...}},
  "hospital": "...",
  "department": "...",
  "doctor": "...",
  "date": "...",
  "diagnosis": ["诊断1", "诊断2"],
  "medications": [
    {{"name": "药品名", "dose": "剂量", "quantity": "数量", "frequency": "频次", "route": "给药途径", "duration": "疗程"}},
    ...
  ],
  "instructions": "医嘱内容"
}}

如果是检查报告(report),输出:
{{
  "document_type": "report",
  "patient": {{"name": "...", "gender": "...", "age": ...}},
  "hospital": "...",
  "department": "...",
  "date": "...",
  "items": [
    {{"name": "项目", "result": "结果", "unit": "单位", "reference_range": "参考范围", "abnormal": "normal|high|low"}},
    ...
  ],
  "summary": "总结(简要说明哪些指标异常及可能意义)"
}}

如果类型无法判断,只输出: {{"document_type": "unknown", "raw_excerpt": "前200字"}}"""

    messages = [
        {"role": "system", "content": "你是医学文本结构化助手。只输出严格 JSON,不要任何解释文字。"},
        {"role": "user", "content": prompt},
    ]
    result_text = await llm.chat(messages, temperature=0.1, max_tokens=1500)

    # 解析
    import json
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        # 尝试从 markdown 代码块提取
        m = re.search(r"\{.*\}", result_text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"document_type": "unknown", "raw_response": result_text[:500]}


def _guess_type(raw_text: str) -> str:
    """根据文本内容猜测类型"""
    if any(k in raw_text for k in ["处方", "Rp", "医嘱"]):
        return "prescription"
    if any(k in raw_text for k in ["检验报告", "参考值", "检验医师"]):
        return "report"
    return "other"
