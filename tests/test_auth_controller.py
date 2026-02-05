"""test_auth_controller: 인증 컨트롤러 단위 테스트."""

import pytest
from unittest.mock import MagicMock, patch
from controllers import auth_controller
from models.user_models import User


class TestLogin:
    """로그인 기능 테스트."""

    @pytest.fixture
    def mock_request(self):
        """Mock Request 객체 생성."""
        request = MagicMock()
        request.session = {}
        return request

    @pytest.fixture
    def mock_credentials(self):
        """Mock 로그인 자격 증명."""
        creds = MagicMock()
        creds.email = "test@example.com"
        creds.password = "Password123!"
        return creds

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자 객체."""
        return User(
            id=1,
            email="test@example.com",
            password="$2b$12$hashedpassword",
            nickname="testuser",
            profile_image_url="/assets/default.png",
            deleted_at=None,
            created_at=None,
        )

    @pytest.mark.asyncio
    @patch("controllers.auth_controller.user_models.get_user_by_email")
    @patch("controllers.auth_controller.verify_password")
    @patch("controllers.auth_controller.session_models.create_session")
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_login_success(
        self,
        mock_timestamp,
        mock_create_session,
        mock_verify,
        mock_get_user,
        mock_request,
        mock_credentials,
        mock_user,
    ):
        """올바른 자격 증명으로 로그인 성공."""
        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        mock_create_session.return_value = None

        result = await auth_controller.login(mock_credentials, mock_request)

        assert result["code"] == "LOGIN_SUCCESS"
        assert "user" in result["data"]
        assert mock_request.session["email"] == "test@example.com"

    @pytest.mark.asyncio
    @patch("controllers.auth_controller.user_models.get_user_by_email")
    @patch("controllers.auth_controller.verify_password")
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_login_invalid_password(
        self,
        mock_timestamp,
        mock_verify,
        mock_get_user,
        mock_request,
        mock_credentials,
        mock_user,
    ):
        """잘못된 비밀번호로 로그인 실패."""
        from fastapi import HTTPException

        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await auth_controller.login(mock_credentials, mock_request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("controllers.auth_controller.user_models.get_user_by_email")
    @patch("controllers.auth_controller.verify_password")
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_login_user_not_found(
        self, mock_timestamp, mock_verify, mock_get_user, mock_request, mock_credentials
    ):
        """존재하지 않는 사용자로 로그인 시도."""
        from fastapi import HTTPException

        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_get_user.return_value = None
        mock_verify.return_value = False  # 타이밍 공격 방지를 위해 항상 검증 수행

        with pytest.raises(HTTPException) as exc_info:
            await auth_controller.login(mock_credentials, mock_request)

        assert exc_info.value.status_code == 401


class TestLogout:
    """로그아웃 기능 테스트."""

    @pytest.fixture
    def mock_request(self):
        """Mock Request 객체 생성."""
        request = MagicMock()
        request.session = {"session_id": "test-session-id", "email": "test@example.com"}
        return request

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자 객체."""
        return User(
            id=1,
            email="test@example.com",
            password="hashed",
            nickname="testuser",
            profile_image_url="/assets/default.png",
            deleted_at=None,
            created_at=None,
        )

    @pytest.mark.asyncio
    @patch("controllers.auth_controller.session_models.delete_session")
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_logout_success(
        self, mock_timestamp, mock_delete_session, mock_request, mock_user
    ):
        """로그아웃 성공."""
        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_delete_session.return_value = None

        result = await auth_controller.logout(mock_user, mock_request)

        assert result["code"] == "LOGOUT_SUCCESS"
        mock_delete_session.assert_called_once_with("test-session-id")


class TestGetMyInfo:
    """내 정보 조회 테스트."""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자 객체."""
        return User(
            id=1,
            email="test@example.com",
            password="hashed",
            nickname="testuser",
            profile_image_url="/assets/default.png",
            deleted_at=None,
            created_at=None,
        )

    @pytest.mark.asyncio
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_get_my_info_success(self, mock_timestamp, mock_user):
        """내 정보 조회 성공."""
        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_request = MagicMock()

        result = await auth_controller.get_my_info(mock_user, mock_request)

        assert result["code"] == "AUTH_SUCCESS"
        assert result["data"]["user"]["email"] == "test@example.com"
        assert result["data"]["user"]["nickname"] == "testuser"
