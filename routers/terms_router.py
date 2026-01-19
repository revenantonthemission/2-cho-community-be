"""terms_router: 이용약관 관련 라우터 모듈.

이용약관 페이지 엔드포인트를 제공합니다.
"""

from fastapi import APIRouter, status
from fastapi.responses import HTMLResponse
from controllers import terms_controller


terms_router = APIRouter(prefix="/v1/terms", tags=["terms"])
"""이용약관 관련 라우터 인스턴스."""


@terms_router.get("", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def get_terms() -> HTMLResponse:
    """이용약관 페이지를 HTML 형식으로 반환합니다.

    Returns:
        이용약관 HTML 페이지를 담은 HTMLResponse.
    """
    html_content = await terms_controller.get_terms()
    return HTMLResponse(content=html_content)
