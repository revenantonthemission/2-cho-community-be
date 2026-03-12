# tests/test_redis_client.py
import pytest
from unittest.mock import AsyncMock, patch

pytest.importorskip("redis", reason="redis는 K8s optional dependency")


@pytest.mark.asyncio
async def test_get_redis_returns_client():
    """Redis 클라이언트 싱글턴 반환 테스트"""
    with patch("utils.redis_client.aioredis") as mock_redis:
        mock_client = AsyncMock()
        mock_redis.from_url.return_value = mock_client

        from utils.redis_client import get_redis, close_redis
        # 모듈 레벨 캐시 초기화
        import utils.redis_client as mod
        mod._redis_client = None

        client = await get_redis("redis://localhost:6379")
        assert client is mock_client
        mock_redis.from_url.assert_called_once_with(
            "redis://localhost:6379", decode_responses=True
        )

        # 두 번째 호출은 캐싱된 클라이언트 반환
        client2 = await get_redis("redis://localhost:6379")
        assert client2 is mock_client
        assert mock_redis.from_url.call_count == 1  # 재호출 안 됨

        await close_redis()
        mock_client.close.assert_called_once()
