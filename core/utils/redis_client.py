"""Redis 연결 관리 — K8s 환경의 Rate Limiter + WebSocket Pub/Sub"""

import asyncio

import redis.asyncio as aioredis

_redis_client = None
_lock = asyncio.Lock()


async def get_redis(redis_url: str) -> aioredis.Redis:
    """Redis 클라이언트 싱글턴 반환 (asyncio.Lock으로 race condition 방지)"""
    global _redis_client
    if _redis_client is None:
        async with _lock:
            if _redis_client is None:
                _redis_client = aioredis.from_url(redis_url, decode_responses=True)
    return _redis_client


async def close_redis():
    """Redis 연결 종료 (앱 shutdown 시 호출)"""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
