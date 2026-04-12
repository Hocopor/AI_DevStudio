import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class WebSocketManager:
    """
    Менеджер WebSocket-соединений.
    Поддерживает глобальный broadcast и broadcast по project_id.
    """

    def __init__(self):
        # Все активные соединения
        self._global: Set[WebSocket] = set()
        # Соединения по проекту
        self._project: Dict[str, Set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, project_id: str = None):
        await ws.accept()
        self._global.add(ws)
        if project_id:
            self._project.setdefault(project_id, set()).add(ws)
        logger.info(f"WS connected. Total: {len(self._global)}")

    def disconnect(self, ws: WebSocket, project_id: str = None):
        self._global.discard(ws)
        if project_id and project_id in self._project:
            self._project[project_id].discard(ws)
        logger.info(f"WS disconnected. Total: {len(self._global)}")

    async def broadcast(self, data: dict, project_id: str = None):
        """Отправить всем или только подписчикам проекта"""
        message = json.dumps(data, ensure_ascii=False, default=str)
        targets = self._project.get(project_id, set()) if project_id else self._global
        dead = set()
        for ws in list(targets):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_to(self, ws: WebSocket, data: dict):
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))
        except Exception:
            self.disconnect(ws)


ws_manager = WebSocketManager()


# ── WS Endpoints ─────────────────────────────────────

async def ws_dashboard(websocket: WebSocket):
    """Глобальный WS — обновления дашборда"""
    from core.auth import decode_token
    token = websocket.query_params.get("token")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(websocket)
    try:
        # Держим соединение, отправляем ping каждые 30 сек
        while True:
            await asyncio.sleep(30)
            await ws_manager.send_to(websocket, {"event": "ping"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def ws_project(websocket: WebSocket, project_id: str):
    """WS для конкретного проекта — обновления Kanban"""
    from core.auth import decode_token
    token = websocket.query_params.get("token")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(websocket, project_id=project_id)
    try:
        while True:
            await asyncio.sleep(30)
            await ws_manager.send_to(websocket, {"event": "ping"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, project_id=project_id)
