"""CSRF Protection Middleware.

Double Submit Cookie 패턴을 사용한 CSRF 방어:
1. 서버는 무작위 토큰을 생성하여 쿠키로 전송
2. 클라이언트는 상태 변경 요청 시 쿠키 토큰을 헤더에 복사하여 전송
3. 서버는 쿠키와 헤더의 토큰이 일치하는지 검증
"""

import secrets
from datetime import UTC, datetime
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.exceptions import forbidden_error


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF 토큰 검증 미들웨어."""

    # 검증이 필요한 HTTP 메서드
    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # 검증 제외 경로 (로그인, 회원가입 등 인증 전 엔드포인트)
    EXEMPT_PATHS = {
        "/v1/auth/session",  # 로그인
        "/v1/users",  # 회원가입
        "/health",  # 헬스체크
    }

    def __init__(self, app, cookie_name: str = "csrf_token", header_name: str = "X-CSRF-Token"):
        """
        Args:
            app: FastAPI 애플리케이션
            cookie_name: CSRF 토큰 쿠키 이름
            header_name: CSRF 토큰 헤더 이름
        """
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """요청을 가로채서 CSRF 토큰 검증."""
        # 1. 보호가 필요한 메서드인지 확인
        if request.method not in self.PROTECTED_METHODS:
            return await self._handle_safe_request(request, call_next)

        # 2. 제외 경로인지 확인
        if self._is_exempt_path(request.url.path):
            return await self._handle_safe_request(request, call_next)

        # 3. CSRF 토큰 검증
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token:
            return self._create_error_response("CSRF token missing")

        # 4. 토큰 일치 검증 (Constant-time comparison)
        if not secrets.compare_digest(cookie_token, header_token):
            return self._create_error_response("CSRF token mismatch")

        # 5. 검증 성공 - 요청 처리
        response = await call_next(request)
        return response

    async def _handle_safe_request(self, request: Request, call_next: Callable) -> Response:
        """안전한 요청 처리 (GET 등) - CSRF 토큰 발급."""
        from core.config import settings

        response = await call_next(request)

        # CSRF 토큰이 없으면 새로 발급
        if self.cookie_name not in request.cookies:
            csrf_token = self._generate_token()
            response.set_cookie(
                key=self.cookie_name,
                value=csrf_token,
                httponly=False,  # JavaScript에서 읽을 수 있어야 함
                secure=settings.HTTPS_ONLY,  # 프로덕션 환경에서는 HTTPS 강제
                samesite="strict",
                max_age=86400,  # 24시간
                path="/",
            )

        return response

    def _is_exempt_path(self, path: str) -> bool:
        """경로가 CSRF 검증 제외 대상인지 확인."""
        return any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS)

    @staticmethod
    def _generate_token() -> str:
        """안전한 무작위 CSRF 토큰 생성."""
        return secrets.token_urlsafe(32)

    def _create_error_response(self, message: str) -> JSONResponse:
        """CSRF 검증 실패 응답 생성."""
        timestamp = datetime.now(UTC).isoformat()
        error = forbidden_error("csrf_validation_failed", timestamp, message)
        return JSONResponse(
            status_code=error.status_code,
            content={
                "code": error.status_code,
                "message": message,
                "data": None,
                "errors": [error.detail],
                "timestamp": timestamp,
            },
        )
