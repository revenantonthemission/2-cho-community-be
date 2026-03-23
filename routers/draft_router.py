"""draft_router: 임시저장 API 라우터."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from dependencies.auth import get_current_user
from dependencies.request_context import get_request_timestamp
from models.draft_models import delete_draft, get_draft, save_draft
from models.user_models import User
from schemas.common import create_response

router = APIRouter(prefix="/v1/drafts", tags=["drafts"])


class SaveDraftRequest(BaseModel):
    """임시저장 요청 모델."""

    title: str | None = None
    content: str | None = None
    category_id: int | None = None


@router.get("/")
async def get_my_draft(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """현재 사용자의 임시저장 조회."""
    timestamp = get_request_timestamp(request)
    draft = await get_draft(current_user.id)
    return create_response(
        "QUERY_SUCCESS",
        "임시저장을 조회했습니다." if draft else "임시저장이 없습니다.",
        data={"draft": draft},
        timestamp=timestamp,
    )


@router.put("/")
async def save_my_draft(
    body: SaveDraftRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """임시저장 생성/갱신 (UPSERT)."""
    timestamp = get_request_timestamp(request)
    draft = await save_draft(
        current_user.id,
        title=body.title,
        content=body.content,
        category_id=body.category_id,
    )
    return create_response(
        "DRAFT_SAVED",
        "임시저장되었습니다.",
        data={"draft": draft},
        timestamp=timestamp,
    )


@router.delete("/")
async def delete_my_draft(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """임시저장 삭제."""
    timestamp = get_request_timestamp(request)
    await delete_draft(current_user.id)
    return create_response(
        "DRAFT_DELETED",
        "임시저장이 삭제되었습니다.",
        timestamp=timestamp,
    )
