"""test_auth_controller: 인증 컨트롤러 단위 테스트 (JWT 기반)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from controllers import auth_controller
from models.user_models import User


class TestLogin:
    """로그인 기능 테스트."""

    @pytest.fixture
    def mock_request(self):
        """Mock Request 객체 생성."""
        request = MagicMock()
        request.state = MagicMock()
        return request

    @pytest.fixture
    def mock_response(self):
        """Mock Response 객체 생성."""
        response = MagicMock()
        response.set_cookie = MagicMock()
        return response

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
    @patch(
        "controllers.auth_controller.user_models.get_user_by_email",
        new_callable=AsyncMock,
    )
    @patch("controllers.auth_controller.verify_password")
    @patch(
        "controllers.auth_controller.token_models.create_refresh_token",
        new_callable=AsyncMock,
    )
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_login_success(
        self,
        mock_timestamp,
        mock_create_refresh,
        mock_verify,
        mock_get_user,
        mock_request,
        mock_response,
        mock_credentials,
        mock_user,
    ):
        """올바른 자격 증명으로 로그인 성공."""
        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        mock_create_refresh.return_value = None

        result = await auth_controller.login(
            mock_credentials, mock_request, mock_response
        )

        assert result["code"] == "LOGIN_SUCCESS"
        assert "access_token" in result["data"]
        assert "user" in result["data"]
        # Refresh Token이 DB에 저장되었는지 확인
        mock_create_refresh.assert_awaited_once()
        assert mock_create_refresh.call_args[0][0] == mock_user.id
        # Refresh Token 쿠키가 설정되었는지 확인
        mock_response.set_cookie.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "controllers.auth_controller.user_models.get_user_by_email",
        new_callable=AsyncMock,
    )
    @patch("controllers.auth_controller.verify_password")
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_login_invalid_password(
        self,
        mock_timestamp,
        mock_verify,
        mock_get_user,
        mock_request,
        mock_response,
        mock_credentials,
        mock_user,
    ):
        """잘못된 비밀번호로 로그인 실패."""
        from fastapi import HTTPException

        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await auth_controller.login(
                mock_credentials, mock_request, mock_response
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch(
        "controllers.auth_controller.user_models.get_user_by_email",
        new_callable=AsyncMock,
    )
    @patch("controllers.auth_controller.verify_password")
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_login_user_not_found(
        self,
        mock_timestamp,
        mock_verify,
        mock_get_user,
        mock_request,
        mock_response,
        mock_credentials,
    ):
        """존재하지 않는 사용자로 로그인 시도."""
        from fastapi import HTTPException

        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_get_user.return_value = None
        mock_verify.return_value = False  # 타이밍 공격 방지를 위해 항상 검증 수행

        with pytest.raises(HTTPException) as exc_info:
            await auth_controller.login(
                mock_credentials, mock_request, mock_response
            )

        assert exc_info.value.status_code == 401


class TestLogout:
    """로그아웃 기능 테스트."""

    @pytest.fixture
    def mock_request(self):
        """Mock Request 객체 생성."""
        request = MagicMock()
        request.cookies = {"refresh_token": "test-refresh-token"}
        request.state = MagicMock()
        return request

    @pytest.fixture
    def mock_response(self):
        """Mock Response 객체 생성."""
        response = MagicMock()
        response.delete_cookie = MagicMock()
        return response

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
    @patch(
        "controllers.auth_controller.token_models.delete_refresh_token",
        new_callable=AsyncMock,
    )
    @patch("controllers.auth_controller.get_request_timestamp")
    async def test_logout_success(
        self,
        mock_timestamp,
        mock_delete_refresh,
        mock_request,
        mock_response,
        mock_user,
    ):
        """로그아웃 성공."""
        mock_timestamp.return_value = "2026-02-04T12:00:00Z"
        mock_delete_refresh.return_value = None

        result = await auth_controller.logout(
            mock_user, mock_request, mock_response
        )

        assert result["code"] == "LOGOUT_SUCCESS"
        mock_delete_refresh.assert_awaited_once_with("test-refresh-token")
        mock_response.delete_cookie.assert_called_once()


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
