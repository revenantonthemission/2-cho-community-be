# request_context: 요청 컨텍스트 의존성
# 미들웨어에서 설정한 요청 정보에 대한 접근을 제공합니다.

from datetime import datetime, timezone
from fastapi import Request


# 요청 타임스탬프를 반환
def get_request_timestamp(request: Request) -> str:
    """
    요청 타임스탬프를 반환

    TimingMiddleware에서 설정한 request_time을 ISO 8601 형식의 문자열로 반환
    미들웨어가 설정되지 않은 경우 현재 시간을 반환
    """
    if hasattr(request.state, "request_time"):
        return request.state.request_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    # 미들웨어가 설정되지 않은 경우 폴백
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# 요청 시간을 datetime 객체로 반환
def get_request_time(request: Request) -> datetime:
    if hasattr(request.state, "request_time"):
        return request.state.request_time
    return datetime.now(timezone.utc)
