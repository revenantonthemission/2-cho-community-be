"""test_rate_limiter: Rate Limiter 미들웨어 단위 테스트."""

import pytest
from middleware.rate_limiter import RateLimiter, RATE_LIMIT_CONFIG, get_client_ip
from unittest.mock import MagicMock


class TestRateLimiter:
    """RateLimiter 클래스 단위 테스트."""

    @pytest.fixture
    def rate_limiter(self):
        """새로운 RateLimiter 인스턴스 생성."""
        return RateLimiter()

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, rate_limiter):
        """첫 번째 요청은 허용되어야 합니다."""
        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1", max_requests=5, window_seconds=60
        )

        assert is_limited is False
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_requests_within_limit(self, rate_limiter):
        """제한 내 요청은 모두 허용되어야 합니다."""
        ip = "192.168.1.2"
        max_requests = 3

        for i in range(max_requests):
            is_limited, remaining = await rate_limiter.is_rate_limited(
                ip=ip, max_requests=max_requests, window_seconds=60
            )
            assert is_limited is False
            assert remaining == max_requests - i - 1

    @pytest.mark.asyncio
    async def test_exceeds_limit(self, rate_limiter):
        """제한 초과 시 차단되어야 합니다."""
        ip = "192.168.1.3"
        max_requests = 2

        # 제한까지 요청
        for _ in range(max_requests):
            await rate_limiter.is_rate_limited(
                ip=ip, max_requests=max_requests, window_seconds=60
            )

        # 제한 초과 요청
        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip=ip, max_requests=max_requests, window_seconds=60
        )

        assert is_limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_different_ips_independent(self, rate_limiter):
        """다른 IP는 독립적으로 제한되어야 합니다."""
        max_requests = 2

        # IP1 제한까지 사용
        for _ in range(max_requests):
            await rate_limiter.is_rate_limited(
                ip="10.0.0.1", max_requests=max_requests, window_seconds=60
            )

        # IP2는 여전히 허용
        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="10.0.0.2", max_requests=max_requests, window_seconds=60
        )

        assert is_limited is False
        assert remaining == 1


class TestGetClientIp:
    """get_client_ip 함수 테스트."""

    def test_direct_client_ip(self):
        """직접 연결된 클라이언트 IP 추출."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "192.168.1.100"

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_forwarded_ip(self):
        """X-Forwarded-For 헤더에서 IP 추출."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = (
            "203.0.113.50, 70.41.3.18, 150.172.238.178"
        )

        ip = get_client_ip(mock_request)
        assert ip == "203.0.113.50"

    def test_no_client(self):
        """클라이언트 정보 없을 때 unknown 반환."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client = None

        ip = get_client_ip(mock_request)
        assert ip == "unknown"


class TestRateLimitConfig:
    """Rate Limit 설정 테스트."""

    def test_auth_endpoints_strict_limits(self):
        """인증 엔드포인트는 엄격한 제한이 있어야 합니다."""
        assert (
            "/v1/auth/login" in RATE_LIMIT_CONFIG
            or "/v1/auth/session" in RATE_LIMIT_CONFIG
        )

    def test_password_endpoint_limited(self):
        """비밀번호 변경 엔드포인트는 제한이 있어야 합니다."""
        assert "/v1/users/me/password" in RATE_LIMIT_CONFIG
        config = RATE_LIMIT_CONFIG["/v1/users/me/password"]
        assert config["max_requests"] <= 5
