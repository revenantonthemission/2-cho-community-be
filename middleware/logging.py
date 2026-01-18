# logging: 요청/응답 로깅 미들웨어
# 모든 HTTP 요청과 응답에 로그를 남긴다.

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# 로거 설정
logger = logging.getLogger("api")
logger.setLevel(logging.INFO)

# 콘솔 핸들러 추가 (없는 경우)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    요청/응답 로깅 미들웨어

    모든 HTTP 요청의 메소드, 경로, 상태 코드, 처리 시간을 로그로 남긴다..
    """

    async def dispatch(self, request: Request, call_next):
        # 요청 시작 시간
        start_time = time.time()

        # 요청 정보 로깅
        logger.info(f"-> {request.method} {request.url.path}")

        # 다음 미들웨어/라우터로 요청 전달
        response = await call_next(request)

        # 처리 시간 계산
        process_time = time.time() - start_time

        # 응답 정보 로깅
        logger.info(
            f"<- {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )

        return response
