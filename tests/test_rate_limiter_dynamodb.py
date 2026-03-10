"""test_rate_limiter_dynamodb: DynamoDB Rate Limiter 단위 테스트.

_get_table()을 mock하여 DynamoDB 의존 없이 로직을 검증한다.
"""

import time
import pytest
from unittest.mock import MagicMock, patch


class TestDynamoDBRateLimiter:
    """DynamoDB Rate Limiter 단위 테스트."""

    @pytest.fixture
    def mock_table(self):
        return MagicMock()

    @pytest.fixture
    def rate_limiter(self):
        from middleware.rate_limiter_dynamodb import DynamoDBRateLimiter

        return DynamoDBRateLimiter()

    @pytest.mark.asyncio
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_first_request_creates_new_window(
        self, mock_get_table, rate_limiter
    ):
        """첫 요청 시 새 윈도우를 생성하고 허용해야 한다."""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": 1}
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
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_within_limit(self, mock_get_table, rate_limiter):
        """제한 내 요청은 허용해야 한다."""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": 3}
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 2

    @pytest.mark.asyncio
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_exceeds_limit(self, mock_get_table, rate_limiter):
        """제한 초과 시 차단해야 한다."""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": 6}
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_expired_window_uses_new_bucket(
        self, mock_get_table, rate_limiter
    ):
        """만료된 윈도우는 새 버킷 키를 사용하므로 카운트가 1부터 시작한다."""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        # 버킷 키 설계: 각 윈도우가 별도 아이템이므로 리셋 없이 새 아이템 생성
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": 1}
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 4
        # 버킷 키 설계에서는 update_item을 1번만 호출 (리셋 불필요)
        assert mock_table.update_item.call_count == 1

    @pytest.mark.asyncio
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_dynamodb_error_allows_request(
        self, mock_get_table, rate_limiter
    ):
        """DynamoDB 오류 시 요청을 허용해야 한다 (fail-open)."""
        mock_get_table.side_effect = Exception("DynamoDB timeout")

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 5

    @pytest.mark.asyncio
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_exact_limit_not_blocked(self, mock_get_table, rate_limiter):
        """정확히 제한 수와 같을 때는 차단하지 않아야 한다."""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": 5}
        }

        is_limited, remaining = await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        assert is_limited is False
        assert remaining == 0

    @pytest.mark.asyncio
    @patch("middleware.rate_limiter_dynamodb._get_table")
    async def test_bucketed_key_includes_bucket_id(
        self, mock_get_table, rate_limiter
    ):
        """버킷 키에 윈도우 버킷 ID가 포함되어야 한다."""
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": 1}
        }

        await rate_limiter.is_rate_limited(
            ip="192.168.1.1:POST:/v1/auth/session",
            max_requests=5,
            window_seconds=60,
        )

        # update_item 호출 인자에서 Key 확인
        call_args = mock_table.update_item.call_args
        key = call_args[1]["Key"]["rate_key"] if "Key" in call_args[1] else call_args[0][0]
        now = int(time.time())
        expected_bucket = now // 60
        assert str(expected_bucket) in key
