"""handler: WebSocket API Gateway Lambda 핸들러.

$connect / $disconnect / $default 라우트를 처리합니다.
모든 라우트가 같은 Lambda로 통합되며, routeKey로 분기합니다.
"""

import json
import logging
import os

from dynamo import save_connection, authenticate_connection, delete_connection, \
    get_user_id_for_connection, get_connections_for_user
from auth import verify_token

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Management API 클라이언트 캐싱 (콜드 스타트 최적화)
_api_gw_client = None


def _get_management_client():
    """API Gateway Management API 클라이언트를 반환합니다 (지연 초기화).

    WS_API_ENDPOINT를 호출 시점에 읽어 테스트 호환성 보장.
    """
    global _api_gw_client
    if _api_gw_client is None:
        import boto3

        _api_gw_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=os.environ.get("WS_API_ENDPOINT", ""),
        )
    return _api_gw_client


def _send_to_connection(connection_id: str, data: dict) -> bool:
    """연결에 JSON 메시지를 전송합니다.

    Returns:
        True 성공, False 실패.
    """
    try:
        client = _get_management_client()
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        client.post_to_connection(ConnectionId=connection_id, Data=payload)
        return True
    except Exception:
        logger.warning("메시지 전송 실패: conn=%s", connection_id, exc_info=True)
        return False


def _handle_connect(connection_id: str) -> dict:
    """$connect: 새 연결을 DynamoDB에 저장합니다 (미인증 상태)."""
    save_connection(connection_id)
    logger.info("연결 수립: %s", connection_id)
    return {"statusCode": 200}


def _handle_disconnect(connection_id: str) -> dict:
    """$disconnect: 연결을 DynamoDB에서 삭제합니다."""
    delete_connection(connection_id)
    logger.info("연결 해제: %s", connection_id)
    return {"statusCode": 200}


def _handle_message(connection_id: str, body: dict) -> dict:
    """$default: 클라이언트 메시지를 처리합니다.

    지원 메시지 타입:
    - auth: JWT 인증 (첫 메시지로 전송 필수)
    - ping: 연결 유지 heartbeat
    - typing_start: 타이핑 시작 이벤트 중계
    - typing_stop: 타이핑 중지 이벤트 중계
    """
    msg_type = body.get("type")

    if msg_type == "auth":
        return _handle_auth(connection_id, body)

    if msg_type == "ping":
        _send_to_connection(connection_id, {"type": "pong"})
        return {"statusCode": 200}

    if msg_type in ("typing_start", "typing_stop"):
        return _handle_typing(connection_id, body, msg_type)

    # 알 수 없는 메시지 타입은 무시 (에러 전파 안 함)
    logger.debug("무시된 메시지 타입: %s", msg_type)
    return {"statusCode": 200}


def _handle_typing(connection_id: str, body: dict, msg_type: str) -> dict:
    """타이핑 이벤트를 상대방에게 중계합니다."""
    conversation_id = body.get("conversation_id")
    if not conversation_id:
        return {"statusCode": 400}

    # 발신자 확인
    sender_id = get_user_id_for_connection(connection_id)
    if not sender_id:
        return {"statusCode": 401}

    # 보안 참고: 상대방 user_id는 클라이언트가 전달 (DynamoDB에서 대화 참여자 미저장).
    # 대화 참여자 검증 없이 타이핑 이벤트를 중계하므로,
    # 악의적 클라이언트가 임의 recipient_id로 타이핑 인디케이터를 보낼 수 있음.
    # 내용 노출은 없으므로 낮은 위험으로 수용 (향후 DynamoDB에 참여자 캐싱으로 개선 가능).
    try:
        recipient_id = int(body.get("recipient_id", ""))
    except (TypeError, ValueError):
        return {"statusCode": 400}

    # 상대방의 모든 연결에 전달
    connections = get_connections_for_user(recipient_id)
    payload = {
        "type": msg_type,
        "conversation_id": conversation_id,
        "sender_id": sender_id,
    }
    for conn_id in connections:
        _send_to_connection(conn_id, payload)

    return {"statusCode": 200}


def _handle_auth(connection_id: str, body: dict) -> dict:
    """인증 메시지를 처리합니다."""
    token = body.get("token", "")
    if not token:
        _send_to_connection(connection_id, {
            "type": "auth_error",
            "message": "토큰이 필요합니다",
        })
        delete_connection(connection_id)
        return {"statusCode": 401}

    user_id = verify_token(token)
    if user_id is None:
        _send_to_connection(connection_id, {
            "type": "auth_error",
            "message": "인증 실패",
        })
        delete_connection(connection_id)
        return {"statusCode": 401}

    authenticate_connection(connection_id, user_id)
    _send_to_connection(connection_id, {"type": "auth_ok", "user_id": user_id})
    logger.info("인증 성공: conn=%s, user=%d", connection_id, user_id)
    return {"statusCode": 200}


def lambda_handler(event, context):
    """Lambda 진입점 — API Gateway WebSocket routeKey로 분기합니다."""
    request_context = event.get("requestContext", {})
    route_key = request_context.get("routeKey")
    connection_id = request_context.get("connectionId")

    if not connection_id:
        logger.error("connectionId 없음")
        return {"statusCode": 400}

    if route_key == "$connect":
        return _handle_connect(connection_id)

    if route_key == "$disconnect":
        return _handle_disconnect(connection_id)

    # $default — 메시지 파싱
    body = {}
    raw_body = event.get("body")
    if raw_body:
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, TypeError):
            logger.warning("잘못된 JSON 메시지: conn=%s", connection_id)
            return {"statusCode": 400}

    return _handle_message(connection_id, body)
