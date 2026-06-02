"""/api/v1/agent - Agent 任务调度"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.agents.medical_agent import get_medical_agent
from app.models.consultation import Consultation
from app.models.message import Message
from app.schemas.agent import (
    SymptomAnalysisRequest, SymptomAnalysisResponse,
    TriageRequest, TriageResponse,
)
from app.utils.logger import logger

router = APIRouter()


@router.post("/analyze", response_model=SymptomAnalysisResponse)
async def analyze_symptoms(
    payload: SymptomAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """结构化症状分析(独立接口,可同步到问诊)"""
    agent = get_medical_agent()
    result = await agent.analyze_symptoms(
        symptoms=payload.symptoms,
        user_context=payload.user_context,
    )

    # 同步结果到 consultation(若提供)
    if payload.consultation_id:
        cons = await db.get(Consultation, payload.consultation_id)
        if cons:
            cons.urgency_level = result.get("urgency_level")
            cons.recommended_department = result.get("department")
            # 把分析报告也存为一条消息,方便回顾
            analysis_msg = Message(
                consultation_id=cons.id,
                role="assistant",
                content=result.get("reply", ""),
                message_type="analysis",
                source_knowledge=result.get("reference_sources"),
                urgency_level=result.get("urgency_level"),
            )
            db.add(analysis_msg)
            await db.commit()
            await db.refresh(analysis_msg)
            logger.info(f"[analyze] 同步到问诊 #{cons.id}: 紧急度={cons.urgency_level}, 科室={cons.recommended_department}")
        else:
            logger.warning(f"[analyze] consultation_id={payload.consultation_id} 不存在,未同步")

    return result


@router.post("/triage", response_model=TriageResponse)
async def triage(
    payload: TriageRequest,
    db: AsyncSession = Depends(get_db),
):
    """快速分诊(可选同步到问诊)"""
    agent = get_medical_agent()
    result = await agent.triage(symptoms=payload.symptoms)

    if hasattr(payload, "consultation_id") and payload.consultation_id:
        cons = await db.get(Consultation, payload.consultation_id)
        if cons:
            cons.urgency_level = result.get("urgency_level")
            cons.recommended_department = result.get("department")
            await db.commit()

    return result
