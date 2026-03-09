"""test_rate_limiter_dynamodb: DynamoDB Rate Limiter 단위 테스트.

boto3 Table을 mock하여 DynamoDB 의존 없이 로직을 검증한다.
"""

import time
import pytest
from unittest.mock import MagicMock
from middleware.rate_limiter_dynamodb import DynamoDBRateLimiter


def _make_limiter(mock_table):
    """Mock table이 주입된 DynamoDBRateLimiter를 생성한다."""
    limiter = DynamoDBRateLimiter.__new__(DynamoDBRateLimiter)
    limiter._table = mock_table
    return limiter


class TestDynamoDBRateLimiter:
    """DynamoDB Rate Limiter 단위 테스트."""

    @pytest.fixture
    def mock_table(self):
        return MagicMock()

    @pytest.fixture
    def rate_limiter(self, mock_table):
        return _make_limiter(mock_table)

    @pytest.mark.asyncio
    async def test_first_request_creates_new_window(self, rate_limiter, mock_table):
        """첫 요청 시 새 윈도우를 생성하고 허용해야 한다."""
        now = int(time.time())
        mock_table.update_item.return_value = {
            "Attributes": {
                "request_count": 1,
                "window_start": now,
            }
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 4
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_within_limit(self, rate_limiter, mock_table):
        """제한 내 요청은 허용해야 한다."""
        now = int(time.time())
        mock_table.update_item.return_value = {
            "Attributes": {
                "request_count": 3,
                "window_start": now,
            }
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 2

    @pytest.mark.asyncio
    async def test_exceeds_limit(self, rate_limiter, mock_table):
        """제한 초과 시 차단해야 한다."""
        now = int(time.time())
        mock_table.update_item.return_value = {
            "Attributes": {
                "request_count": 6,
                "window_start": now,
            }
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_expired_window_resets(self, rate_limiter, mock_table):
        """만료된 윈도우는 리셋되어야 한다."""
        old_time = int(time.time()) - 120  # 2분 전
        now = int(time.time())

        mock_table.update_item.side_effect = [
            # 첫 호출: 기존 윈도우 반환 (만료됨)
            {
                "Attributes": {
                    "request_count": 10,
                    "window_start": old_time,
                }
            },
            # 두 번째 호출: 리셋 후 새 윈도우
            {
                "Attributes": {
                    "request_count": 1,
                    "window_start": now,
                }
            },
        ]

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 4
        # update_item이 2번 호출되어야 한다 (증가 + 리셋)
        assert mock_table.update_item.call_count == 2

    @pytest.mark.asyncio
    async def test_dynamodb_error_allows_request(self, rate_limiter, mock_table):
        """DynamoDB 오류 시 요청을 허용해야 한다 (fail-open)."""
        mock_table.update_item.side_effect = Exception("DynamoDB timeout")

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 5

    @pytest.mark.asyncio
    async def test_exact_limit_not_blocked(self, rate_limiter, mock_table):
        """정확히 제한 수와 같을 때는 차단하지 않아야 한다."""
        now = int(time.time())
        mock_table.update_item.return_value = {
            "Attributes": {
                "request_count": 5,
                "window_start": now,
            }
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 0
