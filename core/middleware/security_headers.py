"""security_headers: HTTP 보안 헤더 미들웨어 모듈.

브라우저 보안 메커니즘을 활성화하는 표준 HTTP 헤더를 모든 응답에 추가합니다.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """HTTP 보안 헤더 미들웨어.

    OWASP 권장 보안 헤더를 모든 응답에 추가합니다.
    HTTPS_ONLY가 활성화된 환경에서는 HSTS 헤더도 포함합니다.
    """

    def __init__(self, app, https_only: bool = False) -> None:
        super().__init__(app)
        self.https_only = https_only

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # MIME 스니핑 방지 — 브라우저가 Content-Type을 무시하고 추측하는 것을 차단
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 클릭재킹 방지 — iframe 삽입 차단
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer 정책 — HTTPS→HTTP 전환 시 전체 URL 노출 방지
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 권한 정책 — 불필요한 브라우저 기능 비활성화
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS — HTTPS 전용 환경에서 브라우저가 항상 HTTPS로 접속하도록 강제
        if self.https_only:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
