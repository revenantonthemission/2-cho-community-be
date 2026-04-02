"""body_limit: 요청 본문 크기 제한 미들웨어 모듈.

K8s 환경에서 nginx 없이 직접 노출되는 API Pod의 DoS 방지를 위해
요청 본문 크기를 제한합니다.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """요청 본문 크기 제한 미들웨어.

    Content-Length 헤더를 검사하여 제한 초과 시 413을 반환합니다.

    Args:
        max_body_size: 최대 본문 크기 (바이트). 기본값 10MB.
    """

    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": f"요청 본문이 {self.max_body_size // (1024 * 1024)}MB 제한을 초과합니다.",
                    }
                },
            )
        return await call_next(request)
