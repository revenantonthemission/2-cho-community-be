"""dm_router: DM(쪽지) API 라우터."""

from fastapi import APIRouter, Depends, Query, Request

from controllers import dm_controller
from dependencies.auth import require_verified_email
from models.user_models import User
from schemas.dm_schemas import CreateConversationRequest, SendMessageRequest

router = APIRouter(prefix="/v1/dms", tags=["dms"])


@router.post("", status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.create_conversation(body.recipient_id, current_user, request)


# 정적 경로를 동적 경로보다 먼저 등록 (FastAPI 라우트 순서)
@router.get("/unread-count")
async def get_unread_count(
    request: Request,
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.get_unread_count(current_user, request)


@router.get("")
async def get_conversations(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.get_conversations(current_user, request, offset, limit)


@router.get("/{conversation_id}")
async def get_messages(
    conversation_id: int,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.get_messages(conversation_id, current_user, request, offset, limit)


@router.post("/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: int,
    body: SendMessageRequest,
    request: Request,
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.send_message(conversation_id, body.content, current_user, request)


@router.delete("/{conversation_id}/messages/{message_id}")
async def delete_message(
    conversation_id: int,
    message_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.delete_message(conversation_id, message_id, current_user, request)


@router.patch("/{conversation_id}/read")
async def mark_read(
    conversation_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.mark_read(conversation_id, current_user, request)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    request: Request,
    current_user: User = Depends(require_verified_email),
):
    return await dm_controller.delete_conversation(conversation_id, current_user, request)
