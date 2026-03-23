"""websocket_pusher: WebSocket 클라이언트에 이벤트를 전송합니다.

best-effort 전송 — 실패해도 예외를 전파하지 않습니다.
알림은 이미 MySQL에 저장되어 있으므로, 푸시 실패 시 다음 폴링에서 수신 가능합니다.

K8s 프로덕션: Redis Pub/Sub
로컬 (DEBUG=True): routers/websocket_router.py의 인메모리 연결 사용
"""

import json
import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)


async def push_to_user(user_id: int, event: dict[str, Any]) -> None:
    """user_id의 모든 WebSocket 연결에 이벤트를 전송합니다 (best-effort)."""
    # K8s: Redis PUBLISH
    if settings.WS_BACKEND == "redis":
        try:
            from utils.redis_client import get_redis

            redis = await get_redis(settings.REDIS_URL)
            payload = json.dumps(event, ensure_ascii=False)
            await redis.publish(f"notify:{user_id}", payload)
        except Exception:
            logger.warning("Redis push 실패 (best-effort)", exc_info=True)
        return

    # 로컬 개발 모드: 인메모리 연결 사용
    if settings.DEBUG:
        try:
            from routers.websocket_router import local_push_to_user

            await local_push_to_user(user_id, event)
        except ImportError:
            pass
        except Exception:
            logger.warning("로컬 WebSocket 푸시 실패", exc_info=True)
