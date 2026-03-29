"""request_id: 요청 상관 ID 미들웨어 모듈.

각 요청에 고유 UUID를 부여하여 로그 추적을 가능하게 합니다.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logging_config import request_id_var


class RequestIdMiddleware(BaseHTTPMiddleware):
    """요청 상관 ID 미들웨어.

    클라이언트가 X-Request-ID 헤더를 보내면 그대로 사용하고,
    없으면 새 UUID를 생성합니다. 응답 헤더에도 포함합니다.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """요청 ID를 생성/전파하고 응답 헤더에 포함합니다."""
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid

        # contextvars에 설정 — 이 요청의 모든 로그에 자동 포함
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)
