"""/api/v1/doctors - 名医录公开接口"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.core.database import get_db
from app.models.doctor import Doctor
from app.schemas.doctor import (
    DoctorOut,
    DoctorListResponse,
    DoctorSearchResult,
    DoctorSearchResponse,
)
from app.services.rag_service import get_rag_service

router = APIRouter()


@router.get("", response_model=DoctorListResponse)
async def list_doctors(
    db: AsyncSession = Depends(get_db),
    department: Optional[str] = None,
    hospital: Optional[str] = None,
    disease: Optional[str] = None,
    city: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """多条件筛选(患者端)"""
    stmt = select(Doctor)
    if department:
        stmt = stmt.where(Doctor.department == department)
    if hospital:
        stmt = stmt.where(Doctor.hospital == hospital)
    if city:
        stmt = stmt.where(Doctor.city == city)
    if disease:
        # 擅长疾病是逗号分隔,模糊匹配
        stmt = stmt.where(Doctor.diseases.like(f"%{disease}%"))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(Doctor.name.like(like), Doctor.bio.like(like), Doctor.diseases.like(like))
        )

    # 总数
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar() or 0

    stmt = stmt.order_by(Doctor.id.desc()).offset((page - 1) * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()
    return DoctorListResponse(items=rows, total=total, page=page, size=size)


@router.get("/search/query", response_model=DoctorSearchResponse)
async def search_doctors(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """向量语义检索(自然语言问名医,例如"北京治肝癌的医生")"""
    rag = get_rag_service()
    raw = await rag.ahybrid_search(query=q, top_k=top_k)
    # 只保留医生类目(索引里以 dr_ 开头)
    candidates: list[tuple[int, float, str]] = []
    for r in raw:
        rid = str(r.get("id", ""))
        if not rid.startswith("dr_"):
            continue
        bio = r.get("content", "")
        candidates.append((int(rid[3:]), r.get("score", 0), bio))

    if not candidates:
        return DoctorSearchResponse(query=q, results=[], total=0)

    # 用一次 DB 查询补全完整字段
    ids = [c[0] for c in candidates]
    rows = (await db.execute(select(Doctor).where(Doctor.id.in_(ids)))).scalars().all()
    mp = {d.id: d for d in rows}

    results = []
    for did, score, bio in candidates:
        d = mp.get(did)
        if not d:
            continue
        snippet = (bio or "")[:200] + ("..." if bio and len(bio) > 200 else "")
        results.append(DoctorSearchResult(
            id=d.id,
            name=d.name,
            department=d.department,
            hospital=d.hospital,
            title=d.title,
            diseases=d.diseases,
            city=d.city,
            avatar=d.avatar,
            bio=d.bio,
            score=round(score, 4),
            snippet=snippet,
        ))
    return DoctorSearchResponse(query=q, results=results, total=len(results))


@router.get("/{doctor_id}", response_model=DoctorOut)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Doctor, doctor_id)
    if not doc:
        raise HTTPException(404, "医生不存在")
    return doc
