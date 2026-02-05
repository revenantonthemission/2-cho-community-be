"""exception_handler: 전역 예외 처리 핸들러 모듈.

처리되지 않은 예외를 일관된 형식의 응답으로 변환합니다.
"""

import uuid
import logging
import traceback
from logging.handlers import RotatingFileHandler
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from dependencies.request_context import get_request_timestamp


logger = logging.getLogger("api")

# 에러 전용 파일 로거 설정
error_logger = logging.getLogger("api.error")
error_logger.setLevel(logging.ERROR)

# RotatingFileHandler: 10MB 단위로 로테이션, 최대 5개 백업 파일
if not error_logger.handlers:
    error_file_handler = RotatingFileHandler(
        "server_error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    error_file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    error_logger.addHandler(error_file_handler)


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

    # 로깅 (항상 수행)
    logger.error(f"[{tracking_id}] Unhandled exception: {exc}")

    # 파일 로깅 (RotatingFileHandler 사용)
    error_logger.error(
        f"[{tracking_id}] Unhandled exception: {exc}\n{traceback.format_exc()}"
    )

    # 프로덕션 환경에서는 상세 에러 숨김
    content = {
        "trackingID": tracking_id,
        "error": "Internal Server Error",
        "timestamp": timestamp,
    }

    # DEBUG 모드에서만 상세 정보 포함
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
    오류 정보에 바이너리 데이터가 포함된 경우 디코딩 오류를 방지하기 위해
    해당 데이터를 문자열 플레이스홀더로 대체합니다.

    Args:
        request: FastAPI Request 객체.
        exc: 발생한 Validation 예외.

    Returns:
        422 Unprocessable Entity 에러 JSON 응답.
    """
    timestamp = get_request_timestamp(request)

    # 에러 상세 정보 복사 (원본 수정 방지)
    errors = exc.errors()
    sanitized_errors = []

    for error in errors:
        error_copy = error.copy()

        # 'input' 필드가 bytes인 경우 처리
        if "input" in error_copy:
            input_val = error_copy["input"]
            if isinstance(input_val, bytes):
                input_len = len(input_val)
                error_copy["input"] = f"<binary data: {input_len} bytes>"
            # 그 외의 경우 jsonable_encoder에서 처리 가능한지 확인 필요 없으나
            # 혹시 모를 다른 비-직렬화 객체에 대한 방어 로직은 jsonable_encoder가 담당함.

        # 'ctx' 필드 내부의 bytes 처리 (재귀적으로 처리하지 않고 단순화)
        if "ctx" in error_copy and isinstance(error_copy["ctx"], dict):
            new_ctx = error_copy["ctx"].copy()
            for k, v in new_ctx.items():
                if isinstance(v, bytes):
                    new_ctx[k] = f"<binary data: {len(v)} bytes>"
            error_copy["ctx"] = new_ctx

        sanitized_errors.append(error_copy)

    # 로깅 (선택 사항 - 너무 길어질 수 있으므로 요약하거나 생략 가능)
    # logger.info(f"Validation error: {sanitized_errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(sanitized_errors), "timestamp": timestamp},
    )
