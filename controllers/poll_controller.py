"""poll_controller: 투표 관련 컨트롤러 모듈."""

from fastapi import Request

from models.user_models import User
from schemas.poll_schemas import PollVoteRequest
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp
from services.poll_service import PollService


async def vote_on_poll(
    post_id: int,
    vote_data: PollVoteRequest,
    current_user: User,
    request: Request,
) -> dict:
    """게시글의 투표에 참여합니다."""
    timestamp = get_request_timestamp(request)

    await PollService.vote_on_poll(
        post_id, vote_data.option_id, current_user.id, timestamp
    )

    return create_response(
        "POLL_VOTED",
        "투표가 완료되었습니다.",
        timestamp=timestamp,
    )
