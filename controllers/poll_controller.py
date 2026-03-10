"""poll_controller: 투표 관련 컨트롤러 모듈."""

from fastapi import HTTPException, Request, status
from pymysql.err import IntegrityError

from models import poll_models
from models.user_models import User
from schemas.poll_schemas import PollVoteRequest
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp


async def vote_on_poll(
    post_id: int,
    vote_data: PollVoteRequest,
    current_user: User,
    request: Request,
) -> dict:
    """게시글의 투표에 참여합니다."""
    timestamp = get_request_timestamp(request)

    poll_id = await poll_models.get_poll_id_by_post_id(post_id)
    if not poll_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "poll_not_found", "timestamp": timestamp},
        )

    # 만료 확인
    poll_data = await poll_models.get_poll_by_post_id(post_id)
    if poll_data and poll_data["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "poll_expired",
                "message": "만료된 투표입니다.",
                "timestamp": timestamp,
            },
        )

    # 선택한 옵션이 해당 투표에 속하는지 검증 (cross-poll vote injection 방지)
    if not await poll_models.option_belongs_to_poll(vote_data.option_id, poll_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_option",
                "message": "해당 투표에 속하지 않는 옵션입니다.",
                "timestamp": timestamp,
            },
        )

    try:
        await poll_models.vote(poll_id, vote_data.option_id, current_user.id)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_voted",
                "message": "이미 투표한 투표입니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "POLL_VOTED",
        "투표가 완료되었습니다.",
        timestamp=timestamp,
    )
