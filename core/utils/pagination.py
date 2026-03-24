"""pagination: 페이지네이션 파라미터 검증 및 SQL 유틸리티."""

from fastapi import HTTPException, status


def escape_like(value: str) -> str:
    """LIKE 패턴의 와일드카드 메타문자(%_)를 이스케이프."""
    return value.replace("%", "\\%").replace("_", "\\_")


def validate_pagination(offset: int, limit: int, timestamp: str) -> None:
    """페이지네이션 파라미터 검증. 유효하지 않으면 400 에러."""
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_offset", "message": "offset은 0 이상이어야 합니다.", "timestamp": timestamp},
        )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_limit", "message": "limit은 1~100 사이여야 합니다.", "timestamp": timestamp},
        )
