"""dm_service: DM(쪽지) 관련 비즈니스 로직을 처리하는 서비스."""

import logging

from pymysql import IntegrityError

from models import dm_models, user_models
from models.block_models import get_blocked_user_ids
from models.dm_models import Conversation
from models.user_models import User
from schemas.common import DEFAULT_PROFILE_IMAGE
from utils.error_codes import ErrorCode
from utils.exceptions import bad_request_error, forbidden_error, not_found_error
from utils.websocket_pusher import push_to_user

logger = logging.getLogger(__name__)


def get_other_user_id(conversation: Conversation, current_user_id: int) -> int:
    """대화에서 상대방의 user_id를 반환합니다."""
    if conversation.participant1_id == current_user_id:
        return conversation.participant2_id
    return conversation.participant1_id


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


async def create_or_get_conversation(
    user_id: int, target_id: int, timestamp: str
) -> tuple[Conversation, bool, dict]:
    """대화를 생성하거나 기존 대화를 반환합니다.

    차단 확인, 상대방 존재 확인, 자기 자신 대화 방지를 포함합니다.

    Returns:
        (Conversation, created, other_user_dict) 튜플.
    """
    # 자기 자신에게 대화 생성 방지
    if user_id == target_id:
        raise bad_request_error(
            ErrorCode.SELF_CONVERSATION, timestamp, "자기 자신에게 쪽지를 보낼 수 없습니다."
        )

    # 상대방 존재 확인
    recipient = await user_models.get_user_by_id(target_id)
    if not recipient or not recipient.is_active:
        raise bad_request_error(
            ErrorCode.RECIPIENT_NOT_FOUND, timestamp, "대화 상대를 찾을 수 없습니다."
        )

    # 양방향 차단 확인 (내가 상대를 차단 OR 상대가 나를 차단)
    my_blocked = await get_blocked_user_ids(user_id)
    their_blocked = await get_blocked_user_ids(target_id)
    if target_id in my_blocked or user_id in their_blocked:
        raise forbidden_error(
            "create_conversation", timestamp, "차단 관계에서는 쪽지를 보낼 수 없습니다."
        )

    # 대화 생성 또는 조회
    try:
        conversation, created = await dm_models.get_or_create_conversation(
            user_id, target_id
        )
    except IntegrityError:
        # 레이스 컨디션: 동시에 같은 대화 생성 시도 → 재시도
        conversation, created = await dm_models.get_or_create_conversation(
            user_id, target_id
        )

    other_user = _build_other_user_dict(recipient)
    return conversation, created, other_user


async def get_conversations(
    user_id: int, timestamp: str, offset: int = 0, limit: int = 20
) -> tuple[list[dict], int]:
    """대화 목록을 조회합니다.

    Returns:
        (conversations, total_count) 튜플.
    """
    conversations, total_count = await dm_models.get_conversations(
        user_id, offset, limit
    )
    return conversations, total_count


async def get_messages(
    conversation_id: int,
    user_id: int,
    timestamp: str,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], dict, int, int]:
    """메시지 목록을 조회하고 읽음 처리를 수행합니다.

    대화 존재 확인, 참여자 검증, 상대방 정보 조회, 읽음 처리 + WebSocket 푸시를 포함합니다.

    Returns:
        (messages, other_user_dict, total_count, read_count) 튜플.
    """
    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, user_id, timestamp)

    messages, total_count = await dm_models.get_messages(
        conversation_id, offset, limit
    )

    # 상대방 정보
    other_user_id = get_other_user_id(conversation, user_id)
    other_user_raw = await user_models.get_user_by_id(other_user_id)
    other_user = _build_other_user_dict(other_user_raw)

    # 상대방 메시지 자동 읽음 처리
    read_count = await dm_models.mark_as_read(conversation_id, user_id)

    # 읽음 처리된 메시지가 있으면 상대방에게 WebSocket 푸시 (best-effort)
    if read_count > 0:
        try:
            await push_to_user(other_user_id, {
                "type": "message_read",
                "conversation_id": conversation_id,
                "reader_id": user_id,
            })
        except Exception:
            logger.warning(
                "message_read WebSocket 푸시 실패 (conversation_id=%d, best-effort)",
                conversation_id,
                exc_info=True,
            )

    return messages, other_user, total_count, read_count


async def mark_read(
    conversation_id: int, user_id: int, timestamp: str
) -> int:
    """대화의 메시지를 읽음 처리하고 WebSocket 푸시를 전송합니다.

    Returns:
        읽음 처리된 메시지 수.
    """
    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, user_id, timestamp)

    read_count = await dm_models.mark_as_read(conversation_id, user_id)

    # 읽음 처리된 메시지가 있으면 상대방에게 WebSocket 푸시 (best-effort)
    if read_count > 0:
        other_user_id = get_other_user_id(conversation, user_id)
        try:
            await push_to_user(other_user_id, {
                "type": "message_read",
                "conversation_id": conversation_id,
                "reader_id": user_id,
            })
        except Exception:
            logger.warning(
                "message_read WebSocket 푸시 실패 (conversation_id=%d, best-effort)",
                conversation_id,
                exc_info=True,
            )

    return read_count


async def send_message_with_validation(
    conversation_id: int, user_id: int, content: str, sender: User, timestamp: str
) -> dict:
    """메시지를 전송합니다 (검증 포함).

    대화 존재 확인, 참여자 검증, 양방향 차단 확인, 상대방 탈퇴 확인 후 메시지 전송.

    Args:
        conversation_id: 대화 ID.
        user_id: 전송자 ID.
        content: 메시지 내용.
        sender: 전송자 User 객체.
        timestamp: 요청 타임스탬프.

    Returns:
        메시지 dict.

    Raises:
        HTTPException: 대화 없음(404), 권한 없음(403), 차단(403), 탈퇴(400).
    """
    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, user_id, timestamp)

    # 양방향 차단 확인
    other_user_id = get_other_user_id(conversation, user_id)
    my_blocked = await get_blocked_user_ids(user_id)
    their_blocked = await get_blocked_user_ids(other_user_id)
    if other_user_id in my_blocked or user_id in their_blocked:
        raise forbidden_error(
            "send_message", timestamp, "차단 관계에서는 쪽지를 보낼 수 없습니다."
        )

    # 상대방 탈퇴 여부 확인
    recipient = await user_models.get_user_by_id(other_user_id)
    if not recipient or not recipient.is_active:
        raise bad_request_error(
            ErrorCode.RECIPIENT_NOT_FOUND, timestamp, "탈퇴한 사용자에게 메시지를 보낼 수 없습니다."
        )

    return await send_message_and_push(conversation, sender, content)


async def send_message_and_push(
    conversation: Conversation, sender: User, content: str
) -> dict:
    """메시지를 전송하고 상대방에게 WebSocket 푸시를 전송합니다.

    WebSocket 푸시는 best-effort로 실패해도 예외를 전파하지 않습니다.
    """
    message = await dm_models.send_message(conversation.id, sender.id, content)

    # 상대방에게 WebSocket 푸시 (best-effort)
    recipient_id = get_other_user_id(conversation, sender.id)
    try:
        await push_to_user(recipient_id, {
            "type": "dm",
            "conversation_id": conversation.id,
            "sender_id": sender.id,
            "sender_nickname": sender.nickname,
            "content": content[:100],
            "created_at": message.get("created_at"),
        })
    except Exception:
        logger.warning(
            "DM WebSocket 푸시 실패 (conversation_id=%d, recipient_id=%d, best-effort)",
            conversation.id,
            recipient_id,
            exc_info=True,
        )

    return message


async def delete_message_with_push(
    conversation_id: int, message_id: int, user_id: int, timestamp: str
) -> None:
    """메시지를 삭제하고 상대방에게 WebSocket 푸시를 전송합니다.

    Args:
        conversation_id: 대화 ID.
        message_id: 삭제할 메시지 ID.
        user_id: 요청 사용자 ID.
        timestamp: 요청 타임스탬프.

    Raises:
        HTTPException: 대화 없음(404), 메시지 없음(404), 권한 없음(403), 이미 삭제(400).
    """
    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, user_id, timestamp)

    result = await dm_models.delete_message(conversation_id, message_id, user_id)
    if result is None:
        raise not_found_error("message", timestamp)
    if result.get("forbidden"):
        raise forbidden_error("delete_message", timestamp, "본인 메시지만 삭제할 수 있습니다.")
    if result.get("already_deleted"):
        raise bad_request_error(ErrorCode.ALREADY_DELETED, timestamp, "이미 삭제된 메시지입니다.")

    # 상대방에게 WebSocket 푸시 (best-effort)
    other_user_id = get_other_user_id(conversation, user_id)
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


async def delete_conversation_with_validation(
    conversation_id: int, user_id: int, timestamp: str
) -> None:
    """대화를 삭제합니다.

    Args:
        conversation_id: 삭제할 대화 ID.
        user_id: 요청 사용자 ID.
        timestamp: 요청 타임스탬프.

    Raises:
        HTTPException: 대화 없음(404), 권한 없음(403).
    """
    conversation = await dm_models.get_conversation_by_id(conversation_id)
    if not conversation:
        raise not_found_error("conversation", timestamp)

    _verify_participant(conversation, user_id, timestamp)

    await dm_models.delete_conversation(conversation_id)
