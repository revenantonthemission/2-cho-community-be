"""Redis 기반 Rate Limiter — Fixed Window Counter (INCR + EXPIRE)"""

import logging
import time

from utils.redis_client import get_redis

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            self._redis = await get_redis(self._redis_url)
        return self._redis

    async def is_rate_limited(self, ip: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        try:
            redis = await self._get_redis()
            bucket_id = int(time.time()) // window_seconds
            key = f"rate:{ip}:{bucket_id}"

            count = await redis.incr(key)
            if count == 1:
                # 첫 요청: 윈도우 만료 + 여유 10초
                await redis.expire(key, window_seconds + 10)

            if count > max_requests:
                return (True, 0)
            return (False, max(0, max_requests - count))

        except Exception:
            # fail-open: Redis 장애 시 요청 허용
            logger.warning("Redis rate limiter error, fail-open", exc_info=True)
            return (False, max_requests)
