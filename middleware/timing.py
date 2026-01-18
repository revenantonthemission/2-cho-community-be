# timing: 요청 타이밍 미들웨어
# 각 요청에 타임스탬프를 주입하여 일관된 시간 정보를 제공합니다.

from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TimingMiddleware(BaseHTTPMiddleware):
    """
    요청 타이밍 미들웨어

    각 요청이 들어올 때 타임스탬프를 request.state에 저장합니다.
    이를 통해 컨트롤러에서 일관된 타임스탬프를 사용할 수 있습니다.
    """

    async def dispatch(self, request: Request, call_next):
        # UTC 시간으로 요청 시간 기록
        request.state.request_time = datetime.now(timezone.utc)

        # 다음 미들웨어/라우터로 요청 전달
        response = await call_next(request)

        return response
