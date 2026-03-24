"""websocket_router: 로컬 개발 전용 WebSocket 엔드포인트.

DEBUG=True일 때만 등록됩니다. 프로덕션에서는 K8s WS Pod이 담당합니다.
인메모리 연결 관리로 Redis 없이 WebSocket 기능을 테스트할 수 있습니다.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.utils.jwt_utils import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

# 인메모리 연결 저장소 (로컬 개발 전용)
# user_id → set[WebSocket]
_connections: dict[int, set[WebSocket]] = {}

_AUTH_TIMEOUT_SEC = 10


async def local_push_to_user(user_id: int, event: dict) -> None:
    """로컬 개발용: 인메모리 연결에 메시지 전송."""
    websockets = _connections.get(user_id, set())
    data = json.dumps(event, ensure_ascii=False)
    stale = set()
    for ws in websockets:
        try:
            await ws.send_text(data)
        except Exception:
            stale.add(ws)
    websockets -= stale


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """로컬 개발용 WebSocket 엔드포인트."""
    await websocket.accept()
    user_id = None

    try:
        # 인증 대기 (타임아웃)
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_AUTH_TIMEOUT_SEC)
            msg = json.loads(raw)
        except TimeoutError:
            await websocket.send_text(json.dumps({"type": "auth_error", "message": "인증 타임아웃"}))
            await websocket.close()
            return

        if msg.get("type") != "auth" or not msg.get("token"):
            await websocket.send_text(json.dumps({"type": "auth_error", "message": "인증 필요"}))
            await websocket.close()
            return

        try:
            payload = decode_access_token(msg["token"])
            user_id = int(payload["sub"])
        except Exception:
            await websocket.send_text(json.dumps({"type": "auth_error", "message": "인증 실패"}))
            await websocket.close()
            return

        # 연결 등록
        if user_id not in _connections:
            _connections[user_id] = set()
        _connections[user_id].add(websocket)

        await websocket.send_text(json.dumps({"type": "auth_ok", "user_id": user_id}))
        logger.info("로컬 WebSocket 연결: user_id=%d", user_id)

        # 메시지 루프 (ping/pong)
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info("로컬 WebSocket 해제: user_id=%s", user_id)
    finally:
        if user_id and user_id in _connections:
            _connections[user_id].discard(websocket)
            if not _connections[user_id]:
                del _connections[user_id]
