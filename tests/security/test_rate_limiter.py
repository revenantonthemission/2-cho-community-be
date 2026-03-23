"""MemoryRateLimiter 단위 테스트.

DB 없이 인메모리 Rate Limiter의 핵심 동작을 검증한다.
"""

from datetime import datetime, timedelta

import pytest

from middleware.rate_limiter import is_valid_ip
from middleware.rate_limiter_memory import MemoryRateLimiter

# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_within_limit():
    """제한 횟수 이내의 요청은 허용되어야 한다."""
    # Arrange
    limiter = MemoryRateLimiter(max_tracked_ips=100)
    max_requests = 5
    window = 60

    # Act — 5회 요청 (제한 이내)
    results = []
    for _ in range(max_requests):
        limited, remaining = await limiter.is_rate_limited("192.168.1.1", max_requests, window)
        results.append((limited, remaining))

    # Assert — 모두 허용, remaining이 4→0으로 감소
    for limited, _ in results:
        assert limited is False
    assert results[0][1] == 4  # 첫 요청 후 남은 횟수
    assert results[-1][1] == 0  # 마지막 요청 후 남은 횟수


@pytest.mark.asyncio
async def test_blocks_over_limit():
    """제한 횟수 초과 시 차단되어야 한다."""
    # Arrange
    limiter = MemoryRateLimiter(max_tracked_ips=100)
    max_requests = 3
    window = 60

    # Act — 3회 허용 후 4번째 요청
    for _ in range(max_requests):
        await limiter.is_rate_limited("10.0.0.1", max_requests, window)

    limited, remaining = await limiter.is_rate_limited("10.0.0.1", max_requests, window)

    # Assert
    assert limited is True
    assert remaining == 0


@pytest.mark.asyncio
async def test_resets_after_window():
    """윈도우 시간 경과 후 카운터가 리셋되어야 한다."""
    # Arrange
    limiter = MemoryRateLimiter(max_tracked_ips=100)
    max_requests = 2
    window = 60

    # 2회 요청으로 제한 도달
    for _ in range(max_requests):
        await limiter.is_rate_limited("10.0.0.2", max_requests, window)

    # Act — 윈도우 경과 시뮬레이션: 기존 타임스탬프를 과거로 변경
    past = datetime.now() - timedelta(seconds=window + 1)
    limiter._requests["10.0.0.2"] = [past, past]

    limited, remaining = await limiter.is_rate_limited("10.0.0.2", max_requests, window)

    # Assert — 윈도우 경과 후 다시 허용
    assert limited is False
    assert remaining == 1


# ---------------------------------------------------------------------------
# 키 독립성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_keys_independent():
    """서로 다른 IP는 독립적인 카운터를 가져야 한다."""
    # Arrange
    limiter = MemoryRateLimiter(max_tracked_ips=100)
    max_requests = 2
    window = 60

    # IP-A: 제한 도달
    for _ in range(max_requests):
        await limiter.is_rate_limited("1.1.1.1", max_requests, window)

    # Act — IP-B: 별도 카운터이므로 허용
    limited, remaining = await limiter.is_rate_limited("2.2.2.2", max_requests, window)

    # Assert
    assert limited is False
    assert remaining == 1


# ---------------------------------------------------------------------------
# 메모리 보호
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_protection_max_ips():
    """max_tracked_ips 초과 시 오래된 IP가 배치 제거되어야 한다."""
    # Arrange — 작은 제한으로 빠른 테스트
    max_ips = 50
    limiter = MemoryRateLimiter(max_tracked_ips=max_ips)

    # max_ips만큼 IP 등록
    for i in range(max_ips):
        await limiter.is_rate_limited(f"10.0.0.{i}", 100, 60)

    assert len(limiter._requests) == max_ips

    # Act — 추가 요청으로 제거 트리거
    await limiter.is_rate_limited("99.99.99.99", 100, 60)

    # Assert — 10% (5개) 제거 후 새 IP 추가 → max_ips - 5 + 1 = 46
    eviction_count = max(1, max_ips // 10)
    expected = max_ips - eviction_count + 1
    assert len(limiter._requests) == expected


# ---------------------------------------------------------------------------
# IP 검증
# ---------------------------------------------------------------------------


def test_ip_validation_valid_ipv4():
    """유효한 IPv4 주소는 True를 반환해야 한다."""
    assert is_valid_ip("192.168.1.1") is True
    assert is_valid_ip("10.0.0.1") is True
    assert is_valid_ip("0.0.0.0") is True


def test_ip_validation_valid_ipv6():
    """유효한 IPv6 주소는 True를 반환해야 한다."""
    assert is_valid_ip("::1") is True
    assert is_valid_ip("2001:db8::1") is True


def test_ip_validation_invalid():
    """유효하지 않은 IP 주소는 False를 반환해야 한다."""
    assert is_valid_ip("not-an-ip") is False
    assert is_valid_ip("999.999.999.999") is False
    assert is_valid_ip("") is False
    assert is_valid_ip("abc.def.ghi.jkl") is False
