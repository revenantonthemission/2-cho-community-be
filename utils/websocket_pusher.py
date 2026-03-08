"""websocket_pusher: REST Lambda에서 WebSocket 클라이언트에 이벤트를 전송합니다.

best-effort 전송 — 실패해도 예외를 전파하지 않습니다.
알림은 이미 MySQL에 저장되어 있으므로, 푸시 실패 시 다음 폴링에서 수신 가능합니다.

프로덕션: DynamoDB + API Gateway Management API
로컬 (DEBUG=True): routers/websocket_router.py의 인메모리 연결 사용
"""

import asyncio
import json
import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

# boto3 클라이언트 지연 초기화 (콜드 스타트 최적화)
_dynamodb_resource = None
_api_gw_client = None


def _get_dynamodb_table():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        import boto3

        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource.Table(settings.WS_DYNAMODB_TABLE)


def _get_api_gw_client():
    global _api_gw_client
    if _api_gw_client is None:
        import boto3

        _api_gw_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=settings.WS_API_GW_ENDPOINT,
        )
    return _api_gw_client


def _sync_push_to_user(user_id: int, event: dict[str, Any]) -> None:
    """동기 버전: DynamoDB 조회 → API GW Management API로 전송."""
    table = _get_dynamodb_table()
    client = _get_api_gw_client()

    response = table.query(
        IndexName="user_id-index",
        KeyConditionExpression="user_id = :uid",
        FilterExpression="authenticated = :auth",
        ExpressionAttributeValues={":uid": user_id, ":auth": True},
    )

    data = json.dumps(event, ensure_ascii=False).encode("utf-8")

    for item in response.get("Items", []):
        conn_id = item["connection_id"]
        try:
            client.post_to_connection(ConnectionId=conn_id, Data=data)
        except client.exceptions.GoneException:
            # 이미 끊어진 연결 정리
            table.delete_item(Key={"connection_id": conn_id})
            logger.debug("stale 연결 삭제: %s", conn_id)
        except Exception:
            logger.warning("WebSocket 전송 실패: conn=%s", conn_id, exc_info=True)


async def push_to_user(user_id: int, event: dict[str, Any]) -> None:
    """user_id의 모든 WebSocket 연결에 이벤트를 전송합니다 (best-effort).

    - 프로덕션: asyncio.to_thread()로 동기 boto3 호출 (이벤트 루프 블로킹 방지)
    - 로컬 (DEBUG=True): 인메모리 연결에 직접 전송
    - 환경변수 미설정 시: 무시
    """
    # 로컬 개발 모드: 인메모리 연결 사용
    if settings.DEBUG and not settings.WS_DYNAMODB_TABLE:
        try:
            from routers.websocket_router import local_push_to_user

            await local_push_to_user(user_id, event)
        except ImportError:
            pass  # websocket_router가 아직 로드되지 않은 경우
        except Exception:
            logger.warning("로컬 WebSocket 푸시 실패", exc_info=True)
        return

    # 프로덕션: DynamoDB + API GW Management API
    if not settings.WS_DYNAMODB_TABLE or not settings.WS_API_GW_ENDPOINT:
        return

    try:
        await asyncio.to_thread(_sync_push_to_user, user_id, event)
    except Exception:
        logger.warning(
            "WebSocket 푸시 실패 (user_id=%d, best-effort)", user_id, exc_info=True
        )
