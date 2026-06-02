"""WebSocket 实时流式对话"""
import json
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect

from app.core.database import AsyncSessionLocal
from app.models.consultation import Consultation
from app.models.message import Message
from app.services.llm_service import get_llm_service
from app.services.rag_service import get_rag_service
from app.agents.medical_agent import get_medical_agent
from app.utils.logger import logger


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self.active[client_id] = ws
        logger.info(f"WS 连接建立: {client_id}")

    def disconnect(self, client_id: str):
        self.active.pop(client_id, None)
        logger.info(f"WS 连接断开: {client_id}")

    async def send(self, client_id: str, data: dict):
        ws = self.active.get(client_id)
        if ws:
            await ws.send_text(json.dumps(data, ensure_ascii=False))


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str = "default"):
    """WebSocket 入口:接收 {"action": ..., "data": ...} 消息"""
    await manager.connect(websocket, client_id)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(client_id, {"type": "error", "message": "无效 JSON"})
                continue

            action = msg.get("action")
            data = msg.get("data", {})

            if action == "chat":
                await handle_chat(client_id, data)
            elif action == "ping":
                await manager.send(client_id, {"type": "pong"})
            else:
                await manager.send(client_id, {"type": "error", "message": f"未知 action: {action}"})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.exception("WS 异常: %s", e)
        manager.disconnect(client_id)


async def handle_chat(client_id: str, data: dict):
    consultation_id = data.get("consultation_id")
    content = data.get("content", "").strip()
    if not content:
        await manager.send(client_id, {"type": "error", "message": "空消息"})
        return

    async with AsyncSessionLocal() as db:
        cons = await db.get(Consultation, consultation_id)
        if not cons:
            await manager.send(client_id, {"type": "error", "message": "问诊不存在"})
            return

        # 保存用户消息
        user_msg = Message(consultation_id=cons.id, role="user", content=content)
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # 拉历史
        from sqlalchemy import select
        stmt = select(Message).where(Message.consultation_id == cons.id).order_by(Message.created_at)
        history = [{"role": m.role, "content": m.content}
                   for m in (await db.execute(stmt)).scalars().all()]

        # 先发送 ack
        await manager.send(client_id, {
            "type": "user_saved",
            "message_id": user_msg.id,
        })

        # 流式:为简化,先一次性推完(mvp)
        agent = get_medical_agent()
        result = await agent.chat(content, conversation_history=history)
        reply = result["reply"]

        # 分片发送(模拟流式)
        chunk_size = 12
        for i in range(0, len(reply), chunk_size):
            await manager.send(client_id, {
                "type": "delta",
                "content": reply[i:i + chunk_size],
            })

        # 保存 AI 消息
        ai_msg = Message(
            consultation_id=cons.id,
            role="assistant",
            content=reply,
            source_knowledge=result.get("source_knowledge"),
            urgency_level=result.get("urgency_level"),
        )
        db.add(ai_msg)
        await db.commit()
        await db.refresh(ai_msg)

        await manager.send(client_id, {
            "type": "done",
            "message_id": ai_msg.id,
            "urgency_level": ai_msg.urgency_level,
            "is_emergency": result.get("is_emergency", False),
            "source_knowledge": ai_msg.source_knowledge,
        })
