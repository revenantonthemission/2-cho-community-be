"""rate_limiter: API 요청 속도 제한 미들웨어.

브루트포스 공격 방지를 위한 IP 기반 Rate Limiting을 제공합니다.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple
import asyncio


class RateLimiter:
    """메모리 기반 Rate Limiter.

    IP 주소별로 요청 횟수를 추적하고 제한합니다.
    프로덕션 환경에서는 Redis 기반으로 교체하는 것을 권장합니다.
    """

    def __init__(self):
        # {ip: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_rate_limited(
        self, ip: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """요청이 속도 제한에 걸리는지 확인합니다.

        Args:
            ip: 클라이언트 IP 주소.
            max_requests: 윈도우 내 최대 요청 수.
            window_seconds: 시간 윈도우 (초).

        Returns:
            (제한 여부, 남은 요청 수) 튜플.
        """
        async with self._lock:
            now = datetime.now()
            window_start = now - timedelta(seconds=window_seconds)

            # 윈도우 내의 요청만 유지
            self._requests[ip] = [
                req_time for req_time in self._requests[ip] if req_time > window_start
            ]

            current_count = len(self._requests[ip])

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
    "/v1/auth/login": {"max_requests": 5, "window_seconds": 60},  # 1분에 5회
    "/v1/auth/signup": {"max_requests": 3, "window_seconds": 60},  # 1분에 3회
    # 사용자 정보 변경 - 중간 제한
    "/v1/users/me/password": {"max_requests": 3, "window_seconds": 60},
    "/v1/users/me/withdraw": {"max_requests": 2, "window_seconds": 60},
    # 게시글 작성 - 스팸 방지
    "/v1/posts": {"max_requests": 10, "window_seconds": 60},  # POST만 적용
}

# 기본 Rate Limit (설정되지 않은 엔드포인트)
DEFAULT_RATE_LIMIT = {"max_requests": 100, "window_seconds": 60}


def get_client_ip(request: Request) -> str:
    """클라이언트 IP를 가져옵니다.

    프록시 뒤에 있는 경우 X-Forwarded-For 헤더를 확인합니다.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate Limiting 미들웨어.

    IP 기반으로 API 요청 속도를 제한합니다.
    """

    async def dispatch(self, request: Request, call_next):
        import os

        # 테스트 환경에서는 Rate Limit 적용 안 함
        if os.environ.get("TESTING") == "true":
            return await call_next(request)

        # GET 요청은 Rate Limit 적용 안 함 (읽기 작업)
        if request.method == "GET":
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
