"""dm_controller: DM(쪽지) 관련 컨트롤러."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from dependencies.request_context import get_request_timestamp
from models import dm_models, user_models
from models.block_models import get_blocked_user_ids
from models.user_models import User
from schemas.common import create_response
from services import dm_service
from utils.error_codes import ErrorCode
from utils.exceptions import bad_request_error, forbidden_error, not_found_error
from utils.formatters import format_datetime
from utils.websocket_pusher import push_to_user

logger = logging.getLogger(__name__)


async def create_conversation(
    recipient_id: int, current_user: User, request: Request
) -> dict | JSONResponse:
    """대화를 생성하거나 기존 대화를 반환합니다."""
    timestamp = get_request_timestamp(request)

    conversation, created, other_user = await dm_service.create_or_get_conversation(
        current_user.id, recipient_id, timestamp
    )

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
    conversations, total_count = await dm_service.get_conversations(
        current_user.id, timestamp, offset, limit
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

    messages, other_user, total_count, _read_count = await dm_service.get_messages(
        conversation_id, current_user.id, timestamp, offset, limit
    )
    has_more = offset + limit < total_count

    return create_response(
        "MESSAGES_LOADED",
        "메시지 목록을 조회했습니다.",
        data={
            "messages": messages,
            "other_user": other_user,
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

    dm_service._verify_participant(conversation, current_user.id, timestamp)

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

    read_count = await dm_service.mark_read(
        conversation_id, current_user.id, timestamp
    )

    return create_response(
        "MESSAGES_READ",
        "메시지를 읽음 처리했습니다.",
        data={"read_count": read_count},
        timestamp=timestamp,
    )


async def delete_message(
    conversation_id: int, message_id: int, current_user: User, request: Request
) -> dict:
    """메시지를 삭제합니다 (soft delete)."""
    timestamp = get_request_timestamp(request)

    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    dm_service._verify_participant(conversation, current_user.id, timestamp)

    result = await dm_models.delete_message(conversation_id, message_id, current_user.id)
    if result is None:
        raise not_found_error("message", timestamp)
    if result.get("forbidden"):
        raise forbidden_error("delete_message", timestamp, "본인 메시지만 삭제할 수 있습니다.")
    if result.get("already_deleted"):
        raise bad_request_error(ErrorCode.ALREADY_DELETED, timestamp, "이미 삭제된 메시지입니다.")

    # 상대방에게 WebSocket 푸시 (best-effort)
    other_user_id = dm_service.get_other_user_id(conversation, current_user.id)
    try:
        await push_to_user(other_user_id, {
            "type": "message_deleted",
            "conversation_id": conversation_id,
            "message_id": message_id,
        })
    except Exception:
        logger.warning(
            "message_deleted WebSocket 푸시 실패 (message_id=%d, best-effort)",
            message_id,
            exc_info=True,
        )

    return create_response(
        "MESSAGE_DELETED",
        "메시지를 삭제했습니다.",
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

    dm_service._verify_participant(conversation, current_user.id, timestamp)

    await dm_models.delete_conversation(conversation_id)

    return create_response(
        "CONVERSATION_DELETED",
        "대화를 삭제했습니다.",
        timestamp=timestamp,
    )
