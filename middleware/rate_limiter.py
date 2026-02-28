"""rate_limiter: API 요청 속도 제한 미들웨어.

브루트포스 공격 방지를 위한 IP 기반 Rate Limiting을 제공합니다.

주요 개선사항:
- LRU 기반 메모리 보호 (최대 IP 수 제한)
- IP 위조 방어 (X-Forwarded-For 검증)
- "unknown" IP에 대한 엄격한 제한
"""

from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple
import asyncio
import logging
import ipaddress

from core.config import settings

logger = logging.getLogger(__name__)


def is_valid_ip(ip_str: str) -> bool:
    """IP 주소 형식을 검증합니다.

    IPv4와 IPv6 모두 지원합니다.

    Args:
        ip_str: 검증할 IP 주소 문자열.

    Returns:
        유효한 IP 주소이면 True, 아니면 False.
    """
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


class RateLimiter:
    """메모리 기반 Rate Limiter (LRU 메모리 보호 적용).

    IP 주소별로 요청 횟수를 추적하고 제한합니다.
    메모리 누수 방지를 위해 최대 추적 IP 수를 제한합니다.

    프로덕션 환경에서는 Redis 기반으로 교체하는 것을 권장합니다.
    """

    def __init__(self, max_tracked_ips: int | None = None):
        """RateLimiter 초기화.

        Args:
            max_tracked_ips: 최대 추적 IP 수 (기본: settings.RATE_LIMIT_MAX_IPS).
        """
        # {ip: [timestamp, ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.max_tracked_ips = (
            max_tracked_ips if max_tracked_ips is not None else settings.RATE_LIMIT_MAX_IPS
        )

    async def is_rate_limited(
        self, ip: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """요청이 속도 제한에 걸리는지 확인합니다.

        배치 제거 방식으로 메모리를 보호합니다:
        1. IP 수가 max_tracked_ips를 초과하면 오래된 IP 10% 일괄 제거
        2. O(1) 평균 성능 보장 (배치 제거로 인한 분할 상환)
        3. "unknown" IP는 더 엄격한 제한 적용

        Args:
            ip: 클라이언트 IP 주소.
            max_requests: 윈도우 내 최대 요청 수.
            window_seconds: 시간 윈도우 (초).

        Returns:
            (제한 여부, 남은 요청 수) 튜플.
        """
        async with self._lock:
            # 메모리 보호: 배치 제거 방식 (성능 최적화)
            if len(self._requests) >= self.max_tracked_ips:
                # 10% (1000개)의 오래된 IP를 일괄 제거
                eviction_count = max(1, self.max_tracked_ips // 10)

                # IP를 마지막 요청 시간 기준으로 정렬 (오래된 순)
                sorted_ips = sorted(
                    self._requests.items(),
                    key=lambda item: max(item[1]) if item[1] else datetime.min
                )

                # 가장 오래된 IP부터 제거
                for ip_to_remove, _ in sorted_ips[:eviction_count]:
                    del self._requests[ip_to_remove]

                logger.warning(
                    f"Rate Limiter 배치 제거: {eviction_count}개 IP 제거 "
                    f"(남은 IP: {len(self._requests)}개)"
                )

            now = datetime.now()
            window_start = now - timedelta(seconds=window_seconds)

            # 윈도우 내의 요청만 유지
            self._requests[ip] = [
                req_time for req_time in self._requests[ip] if req_time > window_start
            ]

            current_count = len(self._requests[ip])

            # "unknown" IP는 더 엄격한 제한 적용 (10회로 제한)
            if ip in ("unknown", "0.0.0.0", ""):
                max_requests = min(max_requests, 10)
                logger.warning(
                    f"Unknown IP 감지: {ip}, 엄격한 제한 적용 (최대 {max_requests}회)"
                )

            if current_count >= max_requests:
                return True, 0

            # 새 요청 기록
            self._requests[ip].append(now)
            return False, max_requests - current_count - 1


# 전역 Rate Limiter 인스턴스
_rate_limiter = RateLimiter()


# 엔드포인트별 Rate Limit 설정
RATE_LIMIT_CONFIG = {
    # 인증 관련 - 엄격한 제한 (브루트포스 방지)
    "/v1/auth/session": {"max_requests": 5, "window_seconds": 60},  # 1분에 5회
    "/v1/users/": {"max_requests": 3, "window_seconds": 60},  # 1분에 3회 (회원가입)
    # 사용자 정보 변경 - 중간 제한
    "/v1/users/me/password": {"max_requests": 3, "window_seconds": 60},
    "/v1/users/me": {"max_requests": 2, "window_seconds": 60},  # DELETE (회원 탈퇴)
    # 게시글 작성 - 스팸 방지
    "/v1/posts": {"max_requests": 10, "window_seconds": 60},  # POST만 적용
}

# 기본 Rate Limit (설정되지 않은 엔드포인트)
DEFAULT_RATE_LIMIT = {"max_requests": 100, "window_seconds": 60}


def get_client_ip(request: Request) -> str:
    """클라이언트 IP를 신뢰할 수 있는 방식으로 추출합니다.

    프록시 체인을 고려하여 실제 클라이언트 IP를 추출합니다.
    X-Forwarded-For 위조 공격을 방어하기 위해 신뢰할 수 있는 프록시를 검증합니다.

    처리 순서:
    1. X-Forwarded-For 헤더 확인 (신뢰된 프록시 검증)
    2. X-Real-IP 헤더 확인 (일부 프록시가 사용)
    3. 직접 연결된 클라이언트 IP

    Args:
        request: FastAPI Request 객체.

    Returns:
        클라이언트 IP 주소. 추출 실패 시 "unknown".
    """
    trusted_proxies = settings.TRUSTED_PROXIES

    # X-Forwarded-For 헤더 확인
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2 형식
        # IP 검증: 빈 문자열과 유효하지 않은 IP 제거
        ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
        ips = [ip for ip in ips if is_valid_ip(ip)]

        # 유효한 IP가 없는 경우
        if not ips:
            logger.warning(
                f"X-Forwarded-For 헤더에 유효한 IP 없음: {x_forwarded_for}"
            )
            # Fallback: 직접 연결 IP 확인
            if request.client and request.client.host:
                return request.client.host
            return "unknown"

        # 신뢰할 수 있는 프록시가 설정된 경우, 역순으로 검증
        # (가장 오른쪽부터 신뢰된 프록시 제거)
        if trusted_proxies:
            for ip in reversed(ips):
                if ip not in trusted_proxies:
                    logger.debug(f"실제 클라이언트 IP 추출: {ip} (프록시 검증 완료)")
                    return ip
            # 모든 IP가 신뢰된 프록시인 경우 첫 번째 IP 반환
            logger.warning(
                f"모든 IP가 신뢰된 프록시: {ips}, 첫 번째 IP 반환"
            )
            return ips[0]

        # 신뢰된 프록시 미설정 시 첫 번째 IP 반환 (기본 동작)
        return ips[0]

    # X-Real-IP 헤더 확인 (Nginx 등 일부 프록시가 사용)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()

    # 직접 연결된 클라이언트 IP
    if request.client and request.client.host:
        return request.client.host

    # IP 추출 실패
    logger.warning("클라이언트 IP 추출 실패, 'unknown' 반환")
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate Limiting 미들웨어.

    IP 기반으로 API 요청 속도를 제한합니다.
    """

    async def dispatch(self, request: Request, call_next):
        import os

        # 테스트 환경에서는 Rate Limit 적용 안 함
        if os.environ.get("TESTING") == "true":
            return await call_next(request)

        # GET, OPTIONS 요청은 Rate Limit 적용 안 함
        # OPTIONS: CORS preflight 요청은 브라우저가 자동 생성하므로 제한 불필요
        if request.method in ("GET", "OPTIONS"):
            return await call_next(request)

        # 정적 파일은 제외
        if request.url.path.startswith("/assets"):
            return await call_next(request)

        # Health check 제외
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = get_client_ip(request)
        path = request.url.path

        # 엔드포인트별 설정 확인
        config = RATE_LIMIT_CONFIG.get(path, DEFAULT_RATE_LIMIT)

        is_limited, remaining = await _rate_limiter.is_rate_limited(
            ip=client_ip,
            max_requests=config["max_requests"],
            window_seconds=config["window_seconds"],
        )

        if is_limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "too_many_requests",
                    "message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
                    "retry_after_seconds": config["window_seconds"],
                },
                headers={
                    "Retry-After": str(config["window_seconds"]),
                    "X-RateLimit-Limit": str(config["max_requests"]),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Rate Limit 헤더 추가
        response.headers["X-RateLimit-Limit"] = str(config["max_requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
