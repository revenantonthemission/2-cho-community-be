# tests/integration/test_redis_integration.py
"""Redis 실제 통합 테스트.

실행: pytest tests/integration/ -m integration --no-cov
조건: Redis 실행 필요 (docker-compose.local.yml 또는 K8s)
"""
import asyncio
import os

import pytest

aioredis = pytest.importorskip("redis.asyncio", reason="redis 패키지 필요")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")


def _NEW() -> aioredis.Redis:
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def _can_connect() -> bool:
    try:
        c = _NEW()
        await c.ping()
        await c.close()
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        not asyncio.get_event_loop().run_until_complete(_can_connect()),
        reason=f"Redis 연결 불가 ({REDIS_URL})",
    ),
    pytest.mark.integration,
]


@pytest.fixture
async def rc():
    client = _NEW()
    yield client
    await client.flushdb()
    await client.close()


async def test_rate_limiter_incr_expire_and_isolation(rc):
    """INCR 카운터 증가 + TTL 설정 + 키 간 격리를 한 번에 검증"""
    # 카운터 증가 + TTL
    assert await rc.incr("rate:a") == 1
    await rc.expire("rate:a", 60)
    assert 0 < await rc.ttl("rate:a") <= 60
    assert await rc.incr("rate:a") == 2

    # 다른 키는 독립
    await rc.incr("rate:b")
    assert int(await rc.get("rate:a")) == 2
    assert int(await rc.get("rate:b")) == 1

    # 1초 TTL 만료
    await rc.set("rate:ttl", "1", ex=1)
    await asyncio.sleep(1.1)
    assert await rc.get("rate:ttl") is None


async def test_pubsub_delivery_and_channel_isolation(rc):
    """publish → subscribe 전달 확인 + 채널 간 격리 검증"""
    sub = rc.pubsub()
    await sub.subscribe("ch:target")
    await sub.get_message(timeout=1)  # subscribe 확인 소비

    pub = _NEW()
    await pub.publish("ch:target", '{"event":"hello"}')
    await pub.publish("ch:other", '{"event":"wrong"}')
    await pub.close()

    msg = await sub.get_message(timeout=2)
    assert msg is not None and msg["type"] == "message"
    assert msg["channel"] == "ch:target"
    assert "hello" in msg["data"]

    # ch:other 메시지는 ch:target subscriber에 도달하지 않음
    stray = await sub.get_message(timeout=0.5)
    assert stray is None

    await sub.unsubscribe("ch:target")
    await sub.close()


async def test_connection_resilience():
    """연결 → 닫기 → 재연결이 정상 동작하는지 확인"""
    c1 = _NEW()
    assert await c1.ping() is True
    await c1.close()

    c2 = _NEW()
    assert await c2.ping() is True
    await c2.close()
