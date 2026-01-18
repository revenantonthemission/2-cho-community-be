# exception_handler: 전역 예외 처리 핸들러

import uuid
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from dependencies.request_context import get_request_timestamp

logger = logging.getLogger("api")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    전역 예외 처리 핸들러

    모든 예외를 잡아서 일관된 형식의 500 에러 응답을 반환합니다.
    """
    tracking_id = str(uuid.uuid4())
    timestamp = get_request_timestamp(request)

    # 로깅
    logger.error(f"[{tracking_id}] Unhandled exception: {exc}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "trackingID": tracking_id,
            "error": str(exc),
            "timestamp": timestamp,
        },
    )
