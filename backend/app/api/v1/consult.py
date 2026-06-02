"""/api/v1/consult - 问诊会话 CRUD + 消息"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.user import User
from app.models.consultation import Consultation
from app.models.message import Message
from app.schemas.consultation import (
    ConsultationCreate, ConsultationOut, ConsultationListItem,
    MessageCreate, MessageOut, ChatRequest, ChatResponse,
)
from app.api.deps import get_current_user, get_current_user_optional
from app.agents.medical_agent import get_medical_agent
from app.utils.logger import logger

router = APIRouter()


@router.post("", response_model=ConsultationOut, status_code=201)
async def create_consultation(
    payload: ConsultationCreate,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """创建问诊会话(允许匿名)"""
    cons = Consultation(
        user_id=user.id if user else payload.user_id,
        chief_complaint=payload.chief_complaint,
    )
    db.add(cons)
    await db.commit()
    await db.refresh(cons)

    # 立即插入一条 system 消息作为开场
    sys_msg = Message(
        consultation_id=cons.id,
        role="system",
        content=f"问诊开始,主诉:{payload.chief_complaint}",
        message_type="text",
    )
    db.add(sys_msg)

    # AI 主动发起首轮问询
    try:
        agent = get_medical_agent()
        first_reply = await agent.chat(payload.chief_complaint, conversation_history=[])
        ai_msg = Message(
            consultation_id=cons.id,
            role="assistant",
            content=first_reply["reply"],
            message_type="text",
            source_knowledge=first_reply.get("source_knowledge"),
            urgency_level=first_reply.get("urgency_level"),
        )
        db.add(ai_msg)
    except Exception as e:
        logger.exception("AI 首轮回复失败: %s", e)
        ai_msg = Message(
            consultation_id=cons.id,
            role="assistant",
            content="您好,我是 AI 医学助手。请详细描述您的症状,我会帮您分析。",
            message_type="text",
        )
        db.add(ai_msg)

    await db.commit()
    # 重新查询带消息
    return await _get_consultation_with_messages(db, cons.id)


@router.get("", response_model=list[ConsultationListItem])
async def list_consultations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """我的问诊列表"""
    stmt = (
        select(Consultation, func.count(Message.id).label("msg_count"))
        .outerjoin(Message, Message.consultation_id == Consultation.id)
        .where(Consultation.user_id == user.id)
        .group_by(Consultation.id)
        .order_by(Consultation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ConsultationListItem(
            id=cons.id,
            chief_complaint=cons.chief_complaint,
            status=cons.status,
            urgency_level=cons.urgency_level,
            recommended_department=cons.recommended_department,
            created_at=cons.created_at,
            message_count=msg_count,
        )
        for cons, msg_count in rows
    ]


@router.get("/{consultation_id}", response_model=ConsultationOut)
async def get_consultation(
    consultation_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取问诊详情(本人可访问,匿名问诊可凭 id 访问)"""
    cons = await _get_consultation_with_messages(db, consultation_id)
    if not cons:
        raise HTTPException(404, "问诊不存在")
    if user and cons.user_id and cons.user_id != user.id:
        raise HTTPException(403, "无权访问此问诊")
    return cons


@router.post("/{consultation_id}/messages", response_model=ChatResponse)
async def send_message(
    consultation_id: int,
    payload: MessageCreate,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """发送消息(非流式)"""
    cons = await db.get(Consultation, consultation_id)
    if not cons:
        raise HTTPException(404, "问诊不存在")
    if user and cons.user_id and cons.user_id != user.id:
        raise HTTPException(403, "无权访问")

    # 保存用户消息
    user_msg = Message(
        consultation_id=cons.id,
        role=payload.role,
        content=payload.content,
        message_type=payload.message_type,
    )
    db.add(user_msg)

    # 拉取历史
    hist_stmt = select(Message).where(Message.consultation_id == cons.id).order_by(Message.created_at)
    history_rows = (await db.execute(hist_stmt)).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    # 用户上下文
    user_ctx = None
    if cons.user_id:
        owner = await db.get(User, cons.user_id)
        if owner:
            user_ctx = {
                "age": owner.age, "gender": owner.gender,
                "allergies": owner.allergies, "chronic_diseases": owner.chronic_diseases,
            }

    # AI 回复
    agent = get_medical_agent()
    ai_result = await agent.chat(
        user_message=payload.content,
        conversation_history=history,
        user_context=user_ctx,
    )

    ai_msg = Message(
        consultation_id=cons.id,
        role="assistant",
        content=ai_result["reply"],
        message_type="text",
        source_knowledge=ai_result.get("source_knowledge"),
        urgency_level=ai_result.get("urgency_level"),
    )
    db.add(ai_msg)

    # 更新会话摘要(取最近 3 条对话为 context)
    cons.urgency_level = ai_result.get("urgency_level", cons.urgency_level)
    await db.commit()
    await db.refresh(ai_msg)

    full = await _get_consultation_with_messages(db, cons.id)
    return ChatResponse(
        message=MessageOut.model_validate(ai_msg),
        consultation=ConsultationOut.model_validate(full),
    )


@router.post("/{consultation_id}/close", response_model=ConsultationOut)
async def close_consultation(
    consultation_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    cons = await db.get(Consultation, consultation_id)
    if not cons:
        raise HTTPException(404, "问诊不存在")
    if user and cons.user_id and cons.user_id != user.id:
        raise HTTPException(403, "无权访问")
    cons.status = "closed"
    await db.commit()
    return await _get_consultation_with_messages(db, cons.id)


# ====================== 工具 ======================

async def _get_consultation_with_messages(db: AsyncSession, cons_id: int):
    """获取问诊并 eager-load messages 避免异步 session 下的 lazy load"""
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Consultation)
        .options(selectinload(Consultation.messages))
        .where(Consultation.id == cons_id)
    )
    cons = (await db.execute(stmt)).scalar_one_or_none()
    return cons
