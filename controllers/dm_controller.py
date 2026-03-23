"""dm_controller: DM(쪽지) 관련 컨트롤러."""

from fastapi import Request
from fastapi.responses import JSONResponse

from dependencies.request_context import get_request_timestamp
from models import dm_models
from models.user_models import User
from schemas.common import create_response
from services import dm_service
from utils.formatters import format_datetime


async def create_conversation(recipient_id: int, current_user: User, request: Request) -> dict | JSONResponse:
    """대화를 생성하거나 기존 대화를 반환합니다."""
    timestamp = get_request_timestamp(request)

    # 서비스 레이어에서 자기 자신·차단·상대방 탈퇴 등 모든 사전 검증 포함
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
        # 새로 생성된 경우에만 201 반환 — 클라이언트가 생성/조회를 구분할 수 있도록
        return create_response(
            "CONVERSATION_CREATED",
            "대화가 생성되었습니다.",
            data=response_data,
            timestamp=timestamp,
        )

    # create_response 기본값이 201이므로 JSONResponse로 명시적으로 200 지정
    body = create_response(
        "CONVERSATION_EXISTS",
        "기존 대화를 반환합니다.",
        data=response_data,
        timestamp=timestamp,
    )
    return JSONResponse(content=body, status_code=200)


async def get_conversations(current_user: User, request: Request, offset: int = 0, limit: int = 20) -> dict:
    """대화 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)
    conversations, total_count = await dm_service.get_conversations(current_user.id, timestamp, offset, limit)
    # has_more: 다음 페이지 존재 여부 — 커서 기반이 아닌 offset 방식이므로 단순 비교
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

    # 조회와 동시에 읽음 처리 수행 — 서비스에서 WebSocket 푸시까지 처리
    # _read_count는 컨트롤러 응답에 포함하지 않음 (내부 처리 결과)
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


async def send_message(conversation_id: int, content: str, current_user: User, request: Request) -> dict:
    """메시지를 전송합니다."""
    timestamp = get_request_timestamp(request)

    # 차단 여부·참여자 검증·상대방 탈퇴 확인을 서비스에서 일괄 처리
    message = await dm_service.send_message_with_validation(
        conversation_id, current_user.id, content, current_user, timestamp
    )

    return create_response(
        "MESSAGE_SENT",
        "메시지를 전송했습니다.",
        data={"message": message},
        timestamp=timestamp,
    )


async def mark_read(conversation_id: int, current_user: User, request: Request) -> dict:
    """대화의 메시지를 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)

    # 읽음 처리 후 상대방에게 WebSocket 푸시 — 서비스에서 best-effort로 전송
    read_count = await dm_service.mark_read(conversation_id, current_user.id, timestamp)

    return create_response(
        "MESSAGES_READ",
        "메시지를 읽음 처리했습니다.",
        data={"read_count": read_count},
        timestamp=timestamp,
    )


async def delete_message(conversation_id: int, message_id: int, current_user: User, request: Request) -> dict:
    """메시지를 삭제합니다 (soft delete)."""
    timestamp = get_request_timestamp(request)

    # soft delete 후 상대방에게 실시간 삭제 이벤트 푸시 — 채팅 UI 즉시 반영을 위해
    await dm_service.delete_message_with_push(conversation_id, message_id, current_user.id, timestamp)

    return create_response(
        "MESSAGE_DELETED",
        "메시지를 삭제했습니다.",
        timestamp=timestamp,
    )


async def get_unread_count(current_user: User, request: Request) -> dict:
    """읽지 않은 대화 수를 조회합니다."""
    timestamp = get_request_timestamp(request)
    # 대화 단위 카운트 — 메시지 수가 아닌 미읽은 대화방 수를 반환해 헤더 뱃지에 표시
    unread_count = await dm_models.get_unread_conversation_count(current_user.id)
    return create_response(
        "UNREAD_COUNT",
        "읽지 않은 대화 수를 조회했습니다.",
        data={"unread_count": unread_count},
        timestamp=timestamp,
    )


async def delete_conversation(conversation_id: int, current_user: User, request: Request) -> dict:
    """대화를 삭제합니다."""
    timestamp = get_request_timestamp(request)

    # 참여자 본인만 삭제 가능 — 서비스에서 소유권 검증 후 처리
    await dm_service.delete_conversation_with_validation(conversation_id, current_user.id, timestamp)

    return create_response(
        "CONVERSATION_DELETED",
        "대화를 삭제했습니다.",
        timestamp=timestamp,
    )
