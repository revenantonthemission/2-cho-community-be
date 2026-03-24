"""K8s WebSocket 서버 — Redis pub/sub 기반 실시간 알림"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from core.utils.jwt_utils import decode_access_token

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
AUTH_TIMEOUT = 5  # 인증 타임아웃 (초)

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    """lifespan 이후 초기화 보장된 Redis 클라이언트 반환"""
    assert _redis is not None, "Redis not initialized — lifespan not started"
    return _redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    if _redis:
        await _redis.close()


app = FastAPI(title="Community WebSocket", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "websocket"}


async def _register_connection(conn_id: str, user_id: int):
    """Redis에 연결 등록"""
    try:
        r = _get_redis()
        await r.hset(
            f"ws:conn:{conn_id}",
            mapping={  # type: ignore[misc]
                "user_id": str(user_id),
            },
        )
        await r.expire(f"ws:conn:{conn_id}", 3600)
        await r.sadd(f"ws:user:{user_id}", conn_id)  # type: ignore[misc]
        await r.expire(f"ws:user:{user_id}", 3600)
    except Exception:
        logger.exception("Redis 연결 등록 실패")


async def _unregister_connection(conn_id: str, user_id: int | None):
    """Redis에서 연결 제거"""
    try:
        r = _get_redis()
        await r.delete(f"ws:conn:{conn_id}")
        if user_id:
            await r.srem(f"ws:user:{user_id}", conn_id)  # type: ignore[misc]
    except Exception:
        logger.exception("Redis 연결 해제 실패")


async def _listen_notifications(ws: WebSocket, user_id: int):
    """Redis SUBSCRIBE → WebSocket push"""
    pubsub = _get_redis().pubsub()
    await pubsub.subscribe(f"notify:{user_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await pubsub.unsubscribe(f"notify:{user_id}")
        await pubsub.close()


async def _handle_message(ws: WebSocket, data: dict, conn_id: str, user_id: int):
    """클라이언트 메시지 처리"""
    msg_type = data.get("type")

    if msg_type == "ping":
        await ws.send_json({"type": "pong"})

    elif msg_type in ("typing_start", "typing_stop"):
        recipient_id = data.get("recipient_id")
        if recipient_id:
            payload = json.dumps(
                {
                    "type": msg_type,
                    "sender_id": user_id,
                    "conversation_id": data.get("conversation_id"),
                }
            )
            await _get_redis().publish(f"notify:{recipient_id}", payload)

    elif msg_type in ("message_deleted", "message_read"):
        recipient_id = data.get("recipient_id")
        if recipient_id:
            payload = json.dumps(
                {
                    "type": msg_type,
                    "sender_id": user_id,
                    **{k: v for k, v in data.items() if k not in ("type", "recipient_id")},
                }
            )
            await _get_redis().publish(f"notify:{recipient_id}", payload)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    conn_id = uuid.uuid4().hex
    user_id = None
    listener_task = None

    try:
        # 인증 대기 (AUTH_TIMEOUT 초)
        try:
            auth_data = await asyncio.wait_for(ws.receive_json(), timeout=AUTH_TIMEOUT)
        except TimeoutError:
            await ws.send_json({"type": "auth_error", "message": "auth timeout"})
            await ws.close()
            return

        if auth_data.get("type") != "auth" or not auth_data.get("token"):
            await ws.send_json({"type": "auth_error", "message": "invalid auth"})
            await ws.close()
            return

        # JWT 검증
        try:
            payload = decode_access_token(auth_data["token"])
        except Exception:
            await ws.send_json({"type": "auth_error", "message": "invalid token"})
            await ws.close()
            return

        user_id = int(payload["sub"])
        await _register_connection(conn_id, user_id)
        await ws.send_json({"type": "auth_ok", "user_id": user_id})

        # 알림 리스너 백그라운드 태스크
        listener_task = asyncio.create_task(_listen_notifications(ws, user_id))

        # 메시지 루프
        while True:
            data = await ws.receive_json()
            await _handle_message(ws, data, conn_id, user_id)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        if listener_task:
            listener_task.cancel()
        await _unregister_connection(conn_id, user_id)
