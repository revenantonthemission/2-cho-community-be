"""dm_service: DM(쪽지) 관련 비즈니스 로직을 처리하는 서비스."""

import logging

from models import dm_models
from models.dm_models import Conversation
from models.user_models import User
from utils.websocket_pusher import push_to_user

logger = logging.getLogger(__name__)


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
        })
    except Exception:
        logger.warning(
            "DM WebSocket 푸시 실패 (conversation_id=%d, recipient_id=%d, best-effort)",
            conversation.id,
            recipient_id,
            exc_info=True,
        )

    return message


def get_other_user_id(conversation: Conversation, current_user_id: int) -> int:
    """대화에서 상대방의 user_id를 반환합니다."""
    if conversation.participant1_id == current_user_id:
        return conversation.participant2_id
    return conversation.participant1_id
