"""rate_limiter_dynamodb: DynamoDB 기반 분산 Rate Limiter.

Fixed Window Counter 알고리즘으로 수평 확장된 Lambda 인스턴스 간 상태를 공유한다.
윈도우 버킷을 rate_key에 포함시켜 윈도우 리셋 경쟁 상태를 방지한다.
DynamoDB TTL로 만료된 윈도우를 자동 정리한다.
오류 시 fail-open (요청 허용) 정책을 적용한다.
"""

import asyncio
import logging
import threading
import time
from typing import Tuple

logger = logging.getLogger(__name__)

# DynamoDB 리소스 지연 초기화 (Lambda 콜드 스타트 최적화)
_table = None
_table_lock = threading.Lock()


def _get_table():
    """DynamoDB Table 리소스를 지연 초기화하여 반환한다.

    threading.Lock으로 동시 초기화를 방지한다 (asyncio.to_thread 환경).
    """
    global _table
    if _table is None:
        with _table_lock:
            if _table is None:
                import boto3
                from core.config import settings

                resource = boto3.resource("dynamodb")
                _table = resource.Table(settings.RATE_LIMIT_DYNAMODB_TABLE)
    return _table


class DynamoDBRateLimiter:
    """DynamoDB 기반 분산 Rate Limiter.

    Fixed Window Counter: 윈도우 버킷 ID를 rate_key에 포함시켜
    각 윈도우가 독립된 DynamoDB 아이템이 된다.
    리셋이 필요 없으므로 동시성 경쟁 상태가 원천적으로 방지된다.
    오류 시 fail-open (요청 허용) 정책을 적용한다.
    """

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
        """동기 DynamoDB 호출 (asyncio.to_thread에서 실행).

        윈도우 버킷 ID를 키에 포함시켜 각 윈도우가 별도 아이템이 된다.
        예: "192.168.1.1:POST:/v1/auth/session" + 60초 윈도우
        → "192.168.1.1:POST:/v1/auth/session:28404123" (bucket = now // 60)
        """
        table = _get_table()
        now = int(time.time())

        # 윈도우 버킷: 같은 윈도우의 요청은 같은 bucket_id를 공유
        bucket_id = now // window_seconds
        bucketed_key = f"{rate_key}:{bucket_id}"

        # TTL: 윈도우 종료 + 5분 여유 (DynamoDB TTL은 48시간 이내 삭제)
        ttl = (bucket_id + 1) * window_seconds + 300

        # 원자적 증가: 아이템이 없으면 생성, 있으면 count 증가
        response = table.update_item(
            Key={"rate_key": bucketed_key},
            UpdateExpression=(
                "SET expires_at = if_not_exists(expires_at, :ttl) "
                "ADD request_count :one"
            ),
            ExpressionAttributeValues={
                ":one": 1,
                ":ttl": ttl,
            },
            ReturnValues="ALL_NEW",
        )

        count = int(response["Attributes"]["request_count"])

        if count > max_requests:
            return True, 0

        return False, max_requests - count
