"""Redis 연결 관리 — K8s 환경의 Rate Limiter + WebSocket Pub/Sub

연결 풀링, 재시도 로직, 헬스체크를 포함합니다.
"""

import asyncio
import logging

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None
_lock = asyncio.Lock()

# Redis 연결 재시도 설정
_MAX_RETRIES = 3
_RETRY_DELAY_SEC = 0.5


async def get_redis(redis_url: str) -> aioredis.Redis:
    """Redis 클라이언트 싱글턴 반환 (asyncio.Lock으로 race condition 방지).

    연결 풀링 및 keepalive를 설정하고, 초기 연결 시 ping으로 검증합니다.
    """
    global _redis_client
    if _redis_client is None:
        async with _lock:
            if _redis_client is None:
                client = aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    socket_keepalive=True,
                    max_connections=50,
                    retry_on_timeout=True,
                )
                # 연결 검증 (재시도 포함)
                for attempt in range(1, _MAX_RETRIES + 1):
                    try:
                        await client.ping()
                        logger.info("Redis 연결 완료: %s", redis_url.split("@")[-1])
                        break
                    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
                        if attempt == _MAX_RETRIES:
                            logger.error("Redis 연결 실패 (%d회 시도): %s", _MAX_RETRIES, exc)
                            raise
                        logger.warning(
                            "Redis 연결 재시도 (%d/%d): %s",
                            attempt,
                            _MAX_RETRIES,
                            exc,
                        )
                        await asyncio.sleep(_RETRY_DELAY_SEC * attempt)
                _redis_client = client
    return _redis_client


async def check_redis_health() -> bool:
    """Redis 연결 상태를 확인합니다. readiness probe 등에서 사용."""
    if _redis_client is None:
        return False
    try:
        await _redis_client.ping()
        return True
    except (RedisConnectionError, RedisTimeoutError, OSError):
        return False


async def close_redis() -> None:
    """Redis 연결 종료 (앱 shutdown 시 호출)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis 연결 종료")
