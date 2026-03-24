# tests/test_rate_limiter_redis.py
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("redis", reason="redis는 K8s optional dependency")


@pytest.mark.asyncio
async def test_redis_rate_limiter_allows_under_limit():
    """제한 이하 요청은 허용"""
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 3
    mock_redis.expire.return_value = True

    with patch("core.middleware.rate_limiter_redis.get_redis", return_value=mock_redis):
        from core.middleware.rate_limiter_redis import RedisRateLimiter

        limiter = RedisRateLimiter(redis_url="redis://localhost:6379")
        limiter._redis = mock_redis

        is_limited, remaining = await limiter.is_rate_limited("127.0.0.1:POST:/v1/auth/session", 5, 60)
        assert is_limited is False
        assert remaining == 2  # 5 - 3


@pytest.mark.asyncio
async def test_redis_rate_limiter_blocks_over_limit():
    """제한 초과 요청은 차단"""
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 6

    with patch("core.middleware.rate_limiter_redis.get_redis", return_value=mock_redis):
        from core.middleware.rate_limiter_redis import RedisRateLimiter

        limiter = RedisRateLimiter(redis_url="redis://localhost:6379")
        limiter._redis = mock_redis

        is_limited, remaining = await limiter.is_rate_limited("127.0.0.1:POST:/v1/auth/session", 5, 60)
        assert is_limited is True
        assert remaining == 0


@pytest.mark.asyncio
async def test_redis_rate_limiter_fail_open():
    """Redis 장애 시 요청 허용 (fail-open)"""
    mock_redis = AsyncMock()
    mock_redis.incr.side_effect = ConnectionError("Redis down")

    with patch("core.middleware.rate_limiter_redis.get_redis", return_value=mock_redis):
        from core.middleware.rate_limiter_redis import RedisRateLimiter

        limiter = RedisRateLimiter(redis_url="redis://localhost:6379")
        limiter._redis = mock_redis

        is_limited, remaining = await limiter.is_rate_limited("127.0.0.1:POST:/v1/auth/session", 5, 60)
        assert is_limited is False
        assert remaining == 5


@pytest.mark.asyncio
async def test_redis_rate_limiter_sets_expire_on_first_request():
    """첫 요청(count=1)에서 EXPIRE 설정"""
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 1

    with patch("core.middleware.rate_limiter_redis.get_redis", return_value=mock_redis):
        from core.middleware.rate_limiter_redis import RedisRateLimiter

        limiter = RedisRateLimiter(redis_url="redis://localhost:6379")
        limiter._redis = mock_redis

        await limiter.is_rate_limited("127.0.0.1:POST:/v1/auth/session", 5, 60)
        mock_redis.expire.assert_called_once()
