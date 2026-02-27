"""exception_handler: 전역 예외 처리 핸들러 모듈.

처리되지 않은 예외를 일관된 형식의 응답으로 변환합니다.
"""

import uuid
import logging
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from dependencies.request_context import get_request_timestamp


logger = logging.getLogger("api")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """전역 예외 처리 핸들러.

    모든 예외를 잡아서 일관된 형식의 500 에러 응답을 반환합니다.
    프로덕션 환경(DEBUG=False)에서는 상세 에러 정보를 숨깁니다.

    Args:
        request: FastAPI Request 객체.
        exc: 발생한 예외.

    Returns:
        500 에러 JSON 응답.
    """
    from core.config import settings

    tracking_id = str(uuid.uuid4())
    timestamp = get_request_timestamp(request)

    logger.error(f"[{tracking_id}] Unhandled exception: {exc}\n{traceback.format_exc()}")

    # 프로덕션 환경에서는 상세 에러 숨김
    content: dict[str, str] = {
        "trackingID": tracking_id,
        "error": "Internal Server Error",
        "timestamp": timestamp,
    }

    if settings.DEBUG:
        content["detail"] = str(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """요청 데이터 유효성 검사 예외 처리 핸들러.

    Pydantic 유효성 검사 실패 시 호출됩니다.
    바이너리 데이터가 포함된 경우 직렬화 오류를 방지하기 위해
    문자열 플레이스홀더로 대체합니다.

    Args:
        request: FastAPI Request 객체.
        exc: 발생한 Validation 예외.

    Returns:
        422 Unprocessable Entity 에러 JSON 응답.
    """
    timestamp = get_request_timestamp(request)

    errors = exc.errors()
    sanitized_errors = []

    for error in errors:
        error_copy = error.copy()

        if "input" in error_copy:
            input_val = error_copy["input"]
            if isinstance(input_val, bytes):
                error_copy["input"] = f"<binary data: {len(input_val)} bytes>"

        if "ctx" in error_copy and isinstance(error_copy["ctx"], dict):
            new_ctx = error_copy["ctx"].copy()
            for k, v in new_ctx.items():
                if isinstance(v, bytes):
                    new_ctx[k] = f"<binary data: {len(v)} bytes>"
            error_copy["ctx"] = new_ctx

        sanitized_errors.append(error_copy)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(sanitized_errors), "timestamp": timestamp},
    )
