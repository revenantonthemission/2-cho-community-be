"""rate_limiter_dynamodb: DynamoDB 기반 분산 Rate Limiter.

Fixed Window Counter 알고리즘으로 수평 확장된 Lambda 인스턴스 간 상태를 공유한다.
DynamoDB TTL로 만료된 윈도우를 자동 정리한다.
오류 시 fail-open (요청 허용) 정책을 적용한다.
"""

import asyncio
import logging
import time
from typing import Tuple

logger = logging.getLogger(__name__)

# DynamoDB 리소스 지연 초기화 (Lambda 콜드 스타트 최적화)
_table = None


def _get_table():
    """DynamoDB Table 리소스를 지연 초기화하여 반환한다."""
    global _table
    if _table is None:
        import boto3
        from core.config import settings

        resource = boto3.resource("dynamodb")
        _table = resource.Table(settings.RATE_LIMIT_DYNAMODB_TABLE)
    return _table


class DynamoDBRateLimiter:
    """DynamoDB 기반 분산 Rate Limiter.

    Fixed Window Counter: 윈도우 단위로 요청 수를 카운트한다.
    DynamoDB UpdateItem의 원자적 증가(ADD)로 동시성 안전하다.
    오류 시 fail-open (요청 허용) 정책을 적용한다.
    """

    def __init__(self):
        self._table = _get_table()

    async def is_rate_limited(
        self, ip: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """DynamoDB에서 요청 카운트를 원자적으로 증가시키고 제한 여부를 확인한다."""
        try:
            return await asyncio.to_thread(
                self._check_rate_limit, ip, max_requests, window_seconds
            )
        except Exception:
            # fail-open: DynamoDB 장애 시 요청 허용
            logger.exception("DynamoDB Rate Limiter 오류, 요청 허용 (fail-open)")
            return False, max_requests

    def _check_rate_limit(
        self, rate_key: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """동기 DynamoDB 호출 (asyncio.to_thread에서 실행)."""
        now = int(time.time())
        ttl = now + window_seconds + 300  # 윈도우 + 5분 여유

        # 원자적 증가: 아이템이 없으면 생성, 있으면 count 증가
        response = self._table.update_item(
            Key={"rate_key": rate_key},
            UpdateExpression=(
                "SET window_start = if_not_exists(window_start, :now), "
                "expires_at = :ttl "
                "ADD request_count :one"
            ),
            ExpressionAttributeValues={
                ":now": now,
                ":one": 1,
                ":ttl": ttl,
            },
            ReturnValues="ALL_NEW",
        )

        attrs = response["Attributes"]
        count = int(attrs["request_count"])
        window_start = int(attrs["window_start"])

        # 윈도우 만료 확인: 만료되었으면 리셋
        if now - window_start > window_seconds:
            response = self._table.update_item(
                Key={"rate_key": rate_key},
                UpdateExpression=(
                    "SET request_count = :one, "
                    "window_start = :now, "
                    "expires_at = :ttl"
                ),
                ExpressionAttributeValues={
                    ":one": 1,
                    ":now": now,
                    ":ttl": ttl,
                },
                ReturnValues="ALL_NEW",
            )
            count = 1

        if count > max_requests:
            return True, 0

        return False, max_requests - count
