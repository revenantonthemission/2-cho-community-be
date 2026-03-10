"""dynamo: DynamoDB WebSocket 연결 매핑 관리.

connection_id ↔ user_id 매핑을 DynamoDB에 저장/조회/삭제합니다.
GSI(user_id-index)로 사용자의 모든 활성 연결을 빠르게 조회할 수 있습니다.
"""

import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_dynamodb = None
_table = None

# 미인증 연결의 placeholder user_id (GSI N 타입 요구사항)
_UNAUTHENTICATED_USER_ID = 0

# TTL: 24시간 (좀비 연결 자동 정리)
_TTL_SECONDS = 86400


def _get_table():
    """DynamoDB 테이블 리소스를 반환합니다 (지연 초기화).

    테이블 이름은 호출 시점에 환경변수에서 읽어 테스트 호환성 보장.
    """
    global _dynamodb, _table
    if _table is None:
        if _dynamodb is None:
            _dynamodb = boto3.resource("dynamodb")
        _table = _dynamodb.Table(os.environ.get("DYNAMODB_TABLE", ""))
    return _table


def save_connection(connection_id: str) -> None:
    """새 WebSocket 연결을 저장합니다 (미인증 상태)."""
    table = _get_table()
    table.put_item(Item={
        "connection_id": connection_id,
        "user_id": _UNAUTHENTICATED_USER_ID,
        "authenticated": False,
        "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ttl": int(time.time()) + _TTL_SECONDS,
    })
    logger.debug("연결 저장: %s", connection_id)


def authenticate_connection(connection_id: str, user_id: int) -> None:
    """연결을 인증 완료 상태로 업데이트합니다."""
    table = _get_table()
    try:
        table.update_item(
            Key={"connection_id": connection_id},
            UpdateExpression="SET user_id = :uid, authenticated = :auth",
            ExpressionAttributeValues={":uid": user_id, ":auth": True},
            ConditionExpression="attribute_exists(connection_id)",
        )
        logger.debug("인증 완료: conn=%s, user=%d", connection_id, user_id)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning("인증 실패 — 연결이 존재하지 않음: %s", connection_id)
        else:
            raise


def delete_connection(connection_id: str) -> None:
    """연결을 삭제합니다."""
    table = _get_table()
    table.delete_item(Key={"connection_id": connection_id})
    logger.debug("연결 삭제: %s", connection_id)


def get_user_id_for_connection(connection_id: str) -> int | None:
    """connection_id에 해당하는 인증된 user_id를 반환합니다."""
    table = _get_table()
    response = table.get_item(Key={"connection_id": connection_id})
    item = response.get("Item")
    if not item or not item.get("authenticated"):
        return None
    user_id = item.get("user_id", _UNAUTHENTICATED_USER_ID)
    # DynamoDB는 숫자를 Decimal로 반환 — int 변환 필수 (JSON 직렬화 호환)
    return int(user_id) if user_id != _UNAUTHENTICATED_USER_ID else None


def get_connections_for_user(user_id: int) -> list[str]:
    """사용자의 모든 인증된 connection_id를 반환합니다."""
    if user_id == _UNAUTHENTICATED_USER_ID:
        return []

    table = _get_table()
    response = table.query(
        IndexName="user_id-index",
        KeyConditionExpression="user_id = :uid",
        FilterExpression="authenticated = :auth",
        ExpressionAttributeValues={":uid": user_id, ":auth": True},
    )
    return [item["connection_id"] for item in response.get("Items", [])]
