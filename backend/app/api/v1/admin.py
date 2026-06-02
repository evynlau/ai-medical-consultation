"""/api/v1/admin - 管理员后台接口
需要 admin 权限
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from app.core.database import get_db
from app.models.user import User
from app.models.consultation import Consultation
from app.models.message import Message
from app.models.knowledge import Knowledge
from app.schemas.user import UserOut, UserAdminUpdate
from app.schemas.consultation import ConsultationListItem
from app.schemas.knowledge import KnowledgeCreate, KnowledgeOut
from app.api.deps import get_admin_user, get_doctor_user
from app.services.rag_service import get_rag_service
from app.utils.logger import logger

router = APIRouter()


# ====================== 1. 仪表盘统计 ======================

@router.get("/stats")
async def get_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """仪表盘核心指标"""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=7)

    # 总数
    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_consultations = (await db.execute(select(func.count(Consultation.id)))).scalar()
    total_knowledge = (await db.execute(select(func.count(Knowledge.id)))).scalar()

    # 今日新增
    today_consultations = (await db.execute(
        select(func.count(Consultation.id)).where(Consultation.created_at >= today_start)
    )).scalar()
    today_users = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )).scalar()

    # 本周新增
    week_consultations = (await db.execute(
        select(func.count(Consultation.id)).where(Consultation.created_at >= week_start)
    )).scalar()

    # 紧急病例
    urgent_count = (await db.execute(
        select(func.count(Consultation.id)).where(Consultation.urgency_level >= 4)
    )).scalar()
    urgent_pending = (await db.execute(
        select(func.count(Consultation.id)).where(
            Consultation.urgency_level >= 4,
            Consultation.status == "active"
        )
    )).scalar()

    # 状态分布
    active_consultations = (await db.execute(
        select(func.count(Consultation.id)).where(Consultation.status == "active")
    )).scalar()
    closed_consultations = (await db.execute(
        select(func.count(Consultation.id)).where(Consultation.status == "closed")
    )).scalar()

    # 知识库分类分布
    kb_by_cat = (await db.execute(
        select(Knowledge.category, func.count(Knowledge.id))
        .group_by(Knowledge.category)
    )).all()
    kb_distribution = {cat: count for cat, count in kb_by_cat}

    # 近 7 天问诊趋势
    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        day_end = day + timedelta(days=1)
        count = (await db.execute(
            select(func.count(Consultation.id)).where(
                Consultation.created_at >= day,
                Consultation.created_at < day_end,
            )
        )).scalar()
        trend.append({"date": day.strftime("%m-%d"), "count": count})

    return {
        "overview": {
            "total_users": total_users,
            "total_consultations": total_consultations,
            "total_knowledge": total_knowledge,
            "active_consultations": active_consultations,
            "closed_consultations": closed_consultations,
        },
        "today": {
            "new_consultations": today_consultations,
            "new_users": today_users,
        },
        "week": {
            "new_consultations": week_consultations,
        },
        "urgent": {
            "total": urgent_count,
            "pending": urgent_pending,
        },
        "knowledge_distribution": kb_distribution,
        "consultation_trend_7d": trend,
    }


# ====================== 2. 问诊管理 ======================

@router.get("/consultations", response_model=List[ConsultationListItem])
async def list_all_consultations(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    urgency: Optional[int] = None,
    keyword: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """全平台问诊列表(管理员视角)"""
    stmt = select(
        Consultation,
        func.count(Message.id).label("msg_count")
    ).outerjoin(Message, Message.consultation_id == Consultation.id)

    if status_filter:
        stmt = stmt.where(Consultation.status == status_filter)
    if urgency is not None:
        stmt = stmt.where(Consultation.urgency_level == urgency)
    if user_id:
        stmt = stmt.where(Consultation.user_id == user_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(Consultation.chief_complaint.like(like), Consultation.diagnosis_summary.like(like))
        )

    stmt = stmt.group_by(Consultation.id).order_by(desc(Consultation.created_at)).limit(limit).offset(offset)
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


@router.get("/consultations/{consultation_id}")
async def get_consultation_detail(
    consultation_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """问诊详情(管理员)"""
    from sqlalchemy.orm import selectinload
    stmt = select(Consultation).options(
        selectinload(Consultation.messages)
    ).where(Consultation.id == consultation_id)
    cons = (await db.execute(stmt)).scalar_one_or_none()
    if not cons:
        raise HTTPException(404, "问诊不存在")

    # 关联用户
    user_info = None
    if cons.user_id:
        user = await db.get(User, cons.user_id)
        if user:
            user_info = {
                "id": user.id,
                "username": user.username,
                "age": user.age,
                "gender": user.gender,
                "allergies": user.allergies,
                "chronic_diseases": user.chronic_diseases,
            }

    return {
        "id": cons.id,
        "user": user_info,
        "chief_complaint": cons.chief_complaint,
        "status": cons.status,
        "urgency_level": cons.urgency_level,
        "diagnosis_summary": cons.diagnosis_summary,
        "recommended_department": cons.recommended_department,
        "created_at": cons.created_at,
        "updated_at": cons.updated_at,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "urgency_level": m.urgency_level,
                "source_knowledge": m.source_knowledge,
                "doctor_id": m.doctor_id,
                "created_at": m.created_at,
            } for m in cons.messages
        ]
    }


# ====================== 3. 医生回复 ======================

class DoctorReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    override_urgency: Optional[int] = None  # 可选:覆盖 AI 评估的紧急度
    diagnosis: Optional[str] = None  # 可选:补充诊断


@router.post("/consultations/{consultation_id}/reply")
async def doctor_reply(
    consultation_id: int,
    payload: DoctorReplyRequest,
    doctor: User = Depends(get_doctor_user),
    db: AsyncSession = Depends(get_db),
):
    """医生对问诊进行人工回复(覆盖 AI 答案)"""
    cons = await db.get(Consultation, consultation_id)
    if not cons:
        raise HTTPException(404, "问诊不存在")

    msg = Message(
        consultation_id=consultation_id,
        role="doctor",
        content=payload.content,
        message_type="doctor_reply",
        doctor_id=doctor.id,
    )
    db.add(msg)

    # 可选:覆盖紧急度
    if payload.override_urgency is not None:
        cons.urgency_level = payload.override_urgency
    if payload.diagnosis:
        cons.diagnosis_summary = payload.diagnosis

    # 自动结束问诊(医生回复后)
    cons.status = "closed"
    await db.commit()
    await db.refresh(msg)

    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "doctor_id": doctor.id,
        "doctor_name": doctor.full_name or doctor.username,
        "created_at": msg.created_at,
    }


# ====================== 4. 紧急看板 ======================

@router.get("/emergency")
async def get_emergency_cases(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    only_active: bool = True,
    limit: int = Query(20, ge=1, le=100),
):
    """紧急病例列表(urgency >= 4)"""
    stmt = select(Consultation).where(Consultation.urgency_level >= 4)
    if only_active:
        stmt = stmt.where(Consultation.status == "active")
    stmt = stmt.order_by(desc(Consultation.created_at)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "chief_complaint": c.chief_complaint,
            "urgency_level": c.urgency_level,
            "recommended_department": c.recommended_department,
            "status": c.status,
            "created_at": c.created_at,
        }
        for c in rows
    ]


# ====================== 5. 用户管理 ======================

@router.get("/users", response_model=List[UserOut])
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = None,
    role: Optional[str] = None,  # admin / doctor / user
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(User)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.like(like), User.email.like(like), User.full_name.like(like)))
    if role == "admin":
        stmt = stmt.where(User.is_admin == True)
    elif role == "doctor":
        stmt = stmt.where(User.is_doctor == True)
    elif role == "user":
        stmt = stmt.where(User.is_admin == False, User.is_doctor == False)
    stmt = stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user_admin(
    user_id: int,
    payload: UserAdminUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员修改用户(角色/状态)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return user


# ====================== 6. 知识库管理 ======================

@router.post("/knowledge", response_model=KnowledgeOut, status_code=201)
async def admin_create_knowledge(
    payload: KnowledgeCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新增知识(管理员)"""
    kb = Knowledge(**payload.model_dump())
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    # 重建索引
    await _rebuild_index(db)
    return kb


@router.put("/knowledge/{kb_id}", response_model=KnowledgeOut)
async def admin_update_knowledge(
    kb_id: int,
    payload: KnowledgeCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    kb = await db.get(Knowledge, kb_id)
    if not kb:
        raise HTTPException(404, "知识不存在")
    for k, v in payload.model_dump().items():
        setattr(kb, k, v)
    await db.commit()
    await db.refresh(kb)
    await _rebuild_index(db)
    return kb


@router.delete("/knowledge/{kb_id}", status_code=204)
async def admin_delete_knowledge(
    kb_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    kb = await db.get(Knowledge, kb_id)
    if not kb:
        raise HTTPException(404, "知识不存在")
    await db.delete(kb)
    await db.commit()
    await _rebuild_index(db)
    return None


@router.post("/knowledge/reindex")
async def admin_reindex(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    count = await _rebuild_index(db)
    return {"message": "reindexed", "count": count}


async def _rebuild_index(db: AsyncSession) -> int:
    rows = (await db.execute(select(Knowledge))).scalars().all()
    documents = [
        {
            "id": kb.id, "title": kb.title, "content": kb.content,
            "category": kb.category, "tags": kb.tags or "", "source": kb.source or "",
        }
        for kb in rows
    ]
    rag = get_rag_service()
    return rag.build_index(documents)
