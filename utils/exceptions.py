"""exceptions: API 에러 응답 생성 헬퍼 모듈.

자주 사용되는 HTTP 에러 응답을 표준화된 형식으로 생성합니다.
"""

from fastapi import HTTPException, status


def not_found_error(resource: str, timestamp: str) -> HTTPException:
    """리소스를 찾을 수 없을 때 404 에러를 생성합니다.

    Args:
        resource: 리소스 이름 (예: 'user', 'post', 'comment').
        timestamp: 요청 타임스탬프.

    Returns:
        HTTPException: 404 Not Found 예외.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": f"{resource}_not_found",
            "timestamp": timestamp,
        },
    )


def forbidden_error(
    action: str, timestamp: str, message: str | None = None
) -> HTTPException:
    """권한이 없을 때 403 에러를 생성합니다.

    Args:
        action: 수행하려는 동작 (예: 'edit', 'delete').
        timestamp: 요청 타임스탬프.
        message: 사용자에게 표시할 메시지 (선택).

    Returns:
        HTTPException: 403 Forbidden 예외.
    """
    detail = {
        "error": f"not_authorized_to_{action}",
        "timestamp": timestamp,
    }
    if message:
        detail["message"] = message
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def bad_request_error(
    error_code: str, timestamp: str, message: str | None = None
) -> HTTPException:
    """잘못된 요청에 대한 400 에러를 생성합니다.

    Args:
        error_code: 에러 코드 (예: 'invalid_input', 'no_changes_provided').
        timestamp: 요청 타임스탬프.
        message: 사용자에게 표시할 메시지 (선택).

    Returns:
        HTTPException: 400 Bad Request 예외.
    """
    detail = {
        "error": error_code,
        "timestamp": timestamp,
    }
    if message:
        detail["message"] = message
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def conflict_error(
    resource: str, timestamp: str, message: str | None = None
) -> HTTPException:
    """리소스 충돌 시 409 에러를 생성합니다.

    Args:
        resource: 충돌하는 리소스 (예: 'email', 'nickname').
        timestamp: 요청 타임스탬프.
        message: 사용자에게 표시할 메시지 (선택).

    Returns:
        HTTPException: 409 Conflict 예외.
    """
    detail = {
        "error": f"{resource}_already_exists",
        "timestamp": timestamp,
    }
    if message:
        detail["message"] = message
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )
