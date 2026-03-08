"""WebSocket Pusher 단위 테스트."""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _reset_pusher_globals():
    """테스트 간 모듈 전역 변수 초기화."""
    import utils.websocket_pusher as mod

    mod._dynamodb_resource = None
    mod._api_gw_client = None
    yield


class TestPushToUserProduction:
    """프로덕션 모드 (DynamoDB + API GW Management API) 테스트."""

    @pytest.fixture(autouse=True)
    def _prod_settings(self, monkeypatch):
        monkeypatch.setattr("core.config.settings.WS_DYNAMODB_TABLE", "test-table")
        monkeypatch.setattr("core.config.settings.WS_API_GW_ENDPOINT", "https://test.endpoint")
        monkeypatch.setattr("core.config.settings.DEBUG", False)

    @pytest.mark.asyncio
    async def test_push_sends_to_all_connections(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"connection_id": "conn-1", "user_id": 1, "authenticated": True},
                {"connection_id": "conn-2", "user_id": 1, "authenticated": True},
            ]
        }
        mock_client = MagicMock()

        with (
            patch("utils.websocket_pusher._get_dynamodb_table", return_value=mock_table),
            patch("utils.websocket_pusher._get_api_gw_client", return_value=mock_client),
        ):
            from utils.websocket_pusher import push_to_user

            await push_to_user(1, {"type": "notification", "data": {"test": True}})

        assert mock_client.post_to_connection.call_count == 2

    @pytest.mark.asyncio
    async def test_push_cleans_stale_connections(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"connection_id": "stale-conn", "user_id": 1, "authenticated": True},
            ]
        }
        mock_client = MagicMock()
        # GoneException 시뮬레이션
        gone_exc = type("GoneException", (Exception,), {})
        mock_client.exceptions.GoneException = gone_exc
        mock_client.post_to_connection.side_effect = gone_exc()

        with (
            patch("utils.websocket_pusher._get_dynamodb_table", return_value=mock_table),
            patch("utils.websocket_pusher._get_api_gw_client", return_value=mock_client),
        ):
            from utils.websocket_pusher import push_to_user

            await push_to_user(1, {"type": "notification", "data": {}})

        mock_table.delete_item.assert_called_once_with(Key={"connection_id": "stale-conn"})

    @pytest.mark.asyncio
    async def test_push_handles_send_failure_gracefully(self):
        """전송 실패 시 예외가 전파되지 않아야 합니다."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"connection_id": "conn-1", "user_id": 1, "authenticated": True},
            ]
        }
        mock_client = MagicMock()
        mock_client.exceptions.GoneException = type("GoneException", (Exception,), {})
        mock_client.post_to_connection.side_effect = RuntimeError("network error")

        with (
            patch("utils.websocket_pusher._get_dynamodb_table", return_value=mock_table),
            patch("utils.websocket_pusher._get_api_gw_client", return_value=mock_client),
        ):
            from utils.websocket_pusher import push_to_user

            # 예외 없이 완료되어야 함
            await push_to_user(1, {"type": "notification", "data": {}})

    @pytest.mark.asyncio
    async def test_push_with_no_connections(self):
        """연결이 없는 사용자에게 푸시 시 정상 반환."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_client = MagicMock()

        with (
            patch("utils.websocket_pusher._get_dynamodb_table", return_value=mock_table),
            patch("utils.websocket_pusher._get_api_gw_client", return_value=mock_client),
        ):
            from utils.websocket_pusher import push_to_user

            await push_to_user(999, {"type": "notification", "data": {}})

        mock_client.post_to_connection.assert_not_called()


class TestPushToUserNotConfigured:
    """환경변수 미설정 시 무시."""

    @pytest.fixture(autouse=True)
    def _no_ws_settings(self, monkeypatch):
        monkeypatch.setattr("core.config.settings.WS_DYNAMODB_TABLE", "")
        monkeypatch.setattr("core.config.settings.WS_API_GW_ENDPOINT", "")
        monkeypatch.setattr("core.config.settings.DEBUG", False)

    @pytest.mark.asyncio
    async def test_push_skips_when_not_configured(self):
        from utils.websocket_pusher import push_to_user

        # boto3 호출 없이 조용히 반환
        await push_to_user(1, {"type": "notification", "data": {}})


class TestPushToUserLocalMode:
    """로컬 개발 모드 (DEBUG=True, DynamoDB 미설정)."""

    @pytest.fixture(autouse=True)
    def _local_settings(self, monkeypatch):
        monkeypatch.setattr("core.config.settings.WS_DYNAMODB_TABLE", "")
        monkeypatch.setattr("core.config.settings.WS_API_GW_ENDPOINT", "")
        monkeypatch.setattr("core.config.settings.DEBUG", True)

    @pytest.mark.asyncio
    async def test_push_handles_import_error_gracefully(self):
        """websocket_router가 로드되지 않은 경우에도 예외 없이 반환."""
        from utils.websocket_pusher import push_to_user

        # routers.websocket_router가 존재하지 않아도 ImportError가 전파되지 않아야 함
        await push_to_user(1, {"type": "notification", "data": {}})

    @pytest.mark.asyncio
    async def test_push_calls_local_push(self):
        """websocket_router가 로드된 경우 local_push_to_user를 호출."""
        import sys
        from unittest.mock import AsyncMock

        mock_local_push = AsyncMock()

        # websocket_router 모듈을 mock으로 등록
        mock_module = MagicMock()
        mock_module.local_push_to_user = mock_local_push
        sys.modules["routers.websocket_router"] = mock_module

        try:
            from utils.websocket_pusher import push_to_user

            await push_to_user(1, {"type": "notification", "data": {"test": True}})
            mock_local_push.assert_called_once_with(
                1, {"type": "notification", "data": {"test": True}}
            )
        finally:
            del sys.modules["routers.websocket_router"]
