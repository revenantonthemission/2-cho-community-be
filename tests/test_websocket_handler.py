"""WebSocket Lambda 핸들러 단위 테스트.

ws_handler/ 디렉토리는 별도 Lambda로 배포되므로,
sys.path에 추가하여 import합니다.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# boto3/botocore는 Lambda 런타임에만 존재 — CI에서 import 실패 방지를 위해 mock 주입
if "botocore" not in sys.modules:
    _botocore_mock = MagicMock()
    sys.modules["botocore"] = _botocore_mock
    sys.modules["botocore.exceptions"] = _botocore_mock.exceptions
if "boto3" not in sys.modules:
    sys.modules["boto3"] = MagicMock()

# ws_handler/ 디렉토리를 import 경로에 추가
_ws_dir = str(Path(__file__).resolve().parent.parent / "ws_handler")
if _ws_dir not in sys.path:
    sys.path.insert(0, _ws_dir)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """WebSocket Lambda 환경변수 설정."""
    monkeypatch.setenv("DYNAMODB_TABLE", "test-ws-connections")
    monkeypatch.setenv("WS_API_ENDPOINT", "https://test.execute-api.ap-northeast-2.amazonaws.com/dev")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-jwt")


@pytest.fixture(autouse=True)
def _reset_modules():
    """테스트 간 모듈 캐시 초기화."""
    # 각 테스트 전에 websocket 모듈의 전역 상태 리셋
    mods_to_clear = [k for k in sys.modules if k in ("handler", "dynamo", "auth")]
    for mod in mods_to_clear:
        del sys.modules[mod]
    yield
    # auth._secret_key 캐시 초기화
    try:
        import auth as auth_mod
        auth_mod._secret_key = None
    except ImportError:
        pass


def _make_event(route_key: str, connection_id: str = "conn-123", body: dict | None = None) -> dict:
    """API Gateway WebSocket 이벤트를 생성합니다."""
    event = {
        "requestContext": {
            "routeKey": route_key,
            "connectionId": connection_id,
        }
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


class TestConnect:
    @patch("dynamo.save_connection")
    def test_connect_saves_connection(self, mock_save):
        import handler
        result = handler.lambda_handler(_make_event("$connect"), None)
        assert result["statusCode"] == 200
        mock_save.assert_called_once_with("conn-123")


class TestDisconnect:
    @patch("dynamo.delete_connection")
    def test_disconnect_deletes_connection(self, mock_delete):
        import handler
        result = handler.lambda_handler(_make_event("$disconnect"), None)
        assert result["statusCode"] == 200
        mock_delete.assert_called_once_with("conn-123")


class TestAuth:
    @patch("handler._send_to_connection", return_value=True)
    @patch("dynamo.authenticate_connection")
    @patch("auth.verify_token", return_value=42)
    def test_auth_success(self, mock_verify, mock_auth, mock_send):
        import handler
        event = _make_event("$default", body={"type": "auth", "token": "valid-token"})
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_verify.assert_called_once_with("valid-token")
        mock_auth.assert_called_once_with("conn-123", 42)
        # auth_ok 메시지 전송 확인
        mock_send.assert_called_with("conn-123", {"type": "auth_ok", "user_id": 42})

    @patch("handler._send_to_connection", return_value=True)
    @patch("dynamo.delete_connection")
    @patch("auth.verify_token", return_value=None)
    def test_auth_failure_deletes_connection(self, mock_verify, mock_delete, mock_send):
        import handler
        event = _make_event("$default", body={"type": "auth", "token": "bad-token"})
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 401
        mock_delete.assert_called_once_with("conn-123")
        # auth_error 메시지 전송 확인
        mock_send.assert_called_with("conn-123", {
            "type": "auth_error",
            "message": "인증 실패",
        })

    @patch("handler._send_to_connection", return_value=True)
    @patch("dynamo.delete_connection")
    def test_auth_missing_token(self, mock_delete, mock_send):
        import handler
        event = _make_event("$default", body={"type": "auth"})
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 401
        mock_delete.assert_called_once_with("conn-123")


class TestPingPong:
    @patch("handler._send_to_connection", return_value=True)
    def test_ping_responds_pong(self, mock_send):
        import handler
        event = _make_event("$default", body={"type": "ping"})
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_send.assert_called_once_with("conn-123", {"type": "pong"})


class TestEdgeCases:
    def test_missing_connection_id(self):
        import handler
        event = {"requestContext": {"routeKey": "$connect"}}
        result = handler.lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_invalid_json_body(self):
        import handler
        event = _make_event("$default")
        event["body"] = "not-json{{"
        result = handler.lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_unknown_message_type_ignored(self):
        import handler
        event = _make_event("$default", body={"type": "unknown_type"})
        result = handler.lambda_handler(event, None)
        assert result["statusCode"] == 200

    def test_empty_body(self):
        import handler
        event = _make_event("$default")
        result = handler.lambda_handler(event, None)
        assert result["statusCode"] == 200


class TestAuthModule:
    def test_verify_valid_token(self):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        token = pyjwt.encode(
            {
                "sub": "123",
                "type": "access",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            "test-secret-key-for-jwt",
            algorithm="HS256",
        )

        import auth
        result = auth.verify_token(token)
        assert result == 123

    def test_verify_expired_token(self):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        token = pyjwt.encode(
            {
                "sub": "123",
                "type": "access",
                "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
                "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
            },
            "test-secret-key-for-jwt",
            algorithm="HS256",
        )

        import auth
        result = auth.verify_token(token)
        assert result is None

    def test_verify_wrong_type(self):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        token = pyjwt.encode(
            {
                "sub": "123",
                "type": "refresh",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            "test-secret-key-for-jwt",
            algorithm="HS256",
        )

        import auth
        result = auth.verify_token(token)
        assert result is None

    def test_verify_wrong_secret(self):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        token = pyjwt.encode(
            {
                "sub": "123",
                "type": "access",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            "wrong-secret",
            algorithm="HS256",
        )

        import auth
        result = auth.verify_token(token)
        assert result is None

    def test_verify_missing_sub(self):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        token = pyjwt.encode(
            {
                "type": "access",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            "test-secret-key-for-jwt",
            algorithm="HS256",
        )

        import auth
        result = auth.verify_token(token)
        assert result is None
