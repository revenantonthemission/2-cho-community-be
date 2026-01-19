"""terms_controller: 이용약관 관련 컨트롤러 모듈.

이용약관 HTML 페이지를 제공하는 기능을 담당합니다.
"""

from pathlib import Path
from fastapi import HTTPException, status


# 프로젝트 루트 디렉터리 경로
PROJECT_ROOT = Path(__file__).parent.parent
"""프로젝트 루트 디렉터리의 경로."""

TERMS_HTML_PATH = PROJECT_ROOT / "assets" / "terms.html"
"""이용약관 HTML 파일의 경로."""


async def get_terms() -> str:
    """이용약관 HTML 콘텐츠를 반환합니다.

    Returns:
        이용약관 HTML 문자열.

    Raises:
        HTTPException: 이용약관 파일을 찾을 수 없는 경우 404 Not Found.
    """
    if not TERMS_HTML_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "이용약관 파일을 찾을 수 없습니다."},
        )

    return TERMS_HTML_PATH.read_text(encoding="utf-8")
