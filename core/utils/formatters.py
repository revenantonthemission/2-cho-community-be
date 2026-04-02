"""formatters: 데이터 포맷팅을 위한 유틸리티 모듈."""

import re
from datetime import datetime

# FULLTEXT BOOLEAN MODE 특수문자 이스케이프 패턴
_FULLTEXT_SPECIAL_CHARS = re.compile(r'([+\-><()~*"@])')


def escape_fulltext_query(query: str) -> str:
    """FULLTEXT BOOLEAN MODE 특수문자를 이스케이프합니다."""
    return _FULLTEXT_SPECIAL_CHARS.sub(r"\\\1", query.strip())


def format_datetime(dt: datetime | str | None) -> str | None:
    """datetime 객체를 ISO 8601 포맷 문자열로 변환합니다.

    Args:
        dt: 변환할 datetime 객체 또는 문자열.

    Returns:
        ISO 8601 포맷 문자열 (예: "2024-01-01T12:00:00Z").
        입력이 None이면 None 반환.
        입력이 이미 문자열이면 그대로 반환.
    """
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
