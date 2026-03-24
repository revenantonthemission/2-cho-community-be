"""request_context: 요청 컨텍스트 의존성 모듈.

미들웨어에서 설정한 요청 정보에 대한 접근을 제공합니다.
"""

from datetime import UTC, datetime

from fastapi import Request


def get_request_timestamp(request: Request) -> str:
    """요청 타임스탬프를 ISO 8601 형식 문자열로 반환합니다.

    TimingMiddleware에서 설정한 request_time을 반환하며,
    미들웨어가 설정되지 않은 경우 현재 시간을 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        ISO 8601 형식의 타임스탬프 문자열.
    """
    if hasattr(request.state, "request_time"):
        return request.state.request_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    # 미들웨어가 설정되지 않은 경우 폴백
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_request_time(request: Request) -> datetime:
    """요청 시간을 datetime 객체로 반환합니다.

    TimingMiddleware에서 설정한 request_time을 반환하며,
    미들웨어가 설정되지 않은 경우 현재 시간을 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        요청 시간 datetime 객체.
    """
    if hasattr(request.state, "request_time"):
        return request.state.request_time
    return datetime.now(UTC)
