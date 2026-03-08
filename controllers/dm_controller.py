"""dm_controller: DM(쪽지) 관련 컨트롤러."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from pymysql import IntegrityError

from dependencies.request_context import get_request_timestamp
from models import dm_models, user_models
from models.block_models import get_blocked_user_ids
from models.dm_models import Conversation
from models.user_models import User
from schemas.common import create_response, DEFAULT_PROFILE_IMAGE
from services import dm_service
from utils.exceptions import bad_request_error, forbidden_error, not_found_error
from utils.formatters import format_datetime

logger = logging.getLogger(__name__)


def _verify_participant(
    conversation: Conversation, user_id: int, timestamp: str
) -> None:
    """대화 참여자인지 검증합니다. 참여자가 아니면 403을 raise합니다."""
    if (
        conversation.participant1_id != user_id
        and conversation.participant2_id != user_id
    ):
        raise forbidden_error("access_conversation", timestamp)


def _build_other_user_dict(user: User | None) -> dict:
    """상대방 사용자 정보 딕셔너리를 생성합니다."""
    if user and user.is_active:
        return {
            "user_id": user.id,
            "nickname": user.nickname,
            "profile_image_url": user.profile_image_url or DEFAULT_PROFILE_IMAGE,
        }
    return {
        "user_id": user.id if user else None,
        "nickname": "탈퇴한 사용자",
        "profile_image_url": DEFAULT_PROFILE_IMAGE,
    }


async def create_conversation(
    recipient_id: int, current_user: User, request: Request
) -> dict | JSONResponse:
    """대화를 생성하거나 기존 대화를 반환합니다."""
    timestamp = get_request_timestamp(request)

    # 자기 자신에게 대화 생성 방지
    if current_user.id == recipient_id:
        raise bad_request_error("self_conversation", timestamp, "자기 자신에게 쪽지를 보낼 수 없습니다.")

    # 상대방 존재 확인
    recipient = await user_models.get_user_by_id(recipient_id)
    if not recipient or not recipient.is_active:
        raise bad_request_error("recipient_not_found", timestamp, "대화 상대를 찾을 수 없습니다.")

    # 양방향 차단 확인 (내가 상대를 차단 OR 상대가 나를 차단)
    my_blocked = await get_blocked_user_ids(current_user.id)
    their_blocked = await get_blocked_user_ids(recipient_id)
    if recipient_id in my_blocked or current_user.id in their_blocked:
        raise forbidden_error(
            "create_conversation", timestamp, "차단 관계에서는 쪽지를 보낼 수 없습니다."
        )

    # 대화 생성 또는 조회
    try:
        conversation, created = await dm_models.get_or_create_conversation(
            current_user.id, recipient_id
        )
    except IntegrityError:
        # 레이스 컨디션: 동시에 같은 대화 생성 시도 → 재시도
        conversation, created = await dm_models.get_or_create_conversation(
            current_user.id, recipient_id
        )

    other_user = _build_other_user_dict(recipient)
    response_data = {
        "conversation": {
            "id": conversation.id,
            "other_user": other_user,
            "created_at": format_datetime(conversation.created_at),
        },
    }

    if created:
        return create_response(
            "CONVERSATION_CREATED",
            "대화가 생성되었습니다.",
            data=response_data,
            timestamp=timestamp,
        )

    # 기존 대화 반환 시 200 상태 코드 사용
    body = create_response(
        "CONVERSATION_EXISTS",
        "기존 대화를 반환합니다.",
        data=response_data,
        timestamp=timestamp,
    )
    return JSONResponse(content=body, status_code=200)


async def get_conversations(
    current_user: User, request: Request, offset: int = 0, limit: int = 20
) -> dict:
    """대화 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)
    conversations, total_count = await dm_models.get_conversations(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count
    return create_response(
        "CONVERSATIONS_LOADED",
        "대화 목록을 조회했습니다.",
        data={
            "conversations": conversations,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_messages(
    conversation_id: int,
    current_user: User,
    request: Request,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """대화의 메시지 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, current_user.id, timestamp)

    messages, total_count = await dm_models.get_messages(
        conversation_id, offset, limit
    )
    has_more = offset + limit < total_count

    # 상대방 메시지 자동 읽음 처리
    await dm_models.mark_as_read(conversation_id, current_user.id)

    return create_response(
        "MESSAGES_LOADED",
        "메시지 목록을 조회했습니다.",
        data={
            "messages": messages,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def send_message(
    conversation_id: int, content: str, current_user: User, request: Request
) -> dict:
    """메시지를 전송합니다."""
    timestamp = get_request_timestamp(request)

    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, current_user.id, timestamp)

    # 양방향 차단 확인
    other_user_id = dm_service.get_other_user_id(conversation, current_user.id)
    my_blocked = await get_blocked_user_ids(current_user.id)
    their_blocked = await get_blocked_user_ids(other_user_id)
    if other_user_id in my_blocked or current_user.id in their_blocked:
        raise forbidden_error(
            "send_message", timestamp, "차단 관계에서는 쪽지를 보낼 수 없습니다."
        )

    # 상대방 탈퇴 여부 확인
    recipient = await user_models.get_user_by_id(other_user_id)
    if not recipient or not recipient.is_active:
        raise bad_request_error(
            "recipient_deleted", timestamp, "탈퇴한 사용자에게 메시지를 보낼 수 없습니다."
        )

    message = await dm_service.send_message_and_push(
        conversation, current_user, content
    )

    return create_response(
        "MESSAGE_SENT",
        "메시지를 전송했습니다.",
        data={"message": message},
        timestamp=timestamp,
    )


async def mark_read(
    conversation_id: int, current_user: User, request: Request
) -> dict:
    """대화의 메시지를 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)

    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, current_user.id, timestamp)

    read_count = await dm_models.mark_as_read(conversation_id, current_user.id)

    return create_response(
        "MESSAGES_READ",
        "메시지를 읽음 처리했습니다.",
        data={"read_count": read_count},
        timestamp=timestamp,
    )


async def get_unread_count(current_user: User, request: Request) -> dict:
    """읽지 않은 대화 수를 조회합니다."""
    timestamp = get_request_timestamp(request)
    unread_count = await dm_models.get_unread_conversation_count(current_user.id)
    return create_response(
        "UNREAD_COUNT",
        "읽지 않은 대화 수를 조회했습니다.",
        data={"unread_count": unread_count},
        timestamp=timestamp,
    )


async def delete_conversation(
    conversation_id: int, current_user: User, request: Request
) -> dict:
    """대화를 삭제합니다."""
    timestamp = get_request_timestamp(request)

    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, current_user.id, timestamp)

    await dm_models.delete_conversation(conversation_id)

    return create_response(
        "CONVERSATION_DELETED",
        "대화를 삭제했습니다.",
        timestamp=timestamp,
    )
