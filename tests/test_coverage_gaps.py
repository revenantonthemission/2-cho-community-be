import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

# ==========================================
# Gaps in User Controller
# ==========================================


@pytest.mark.asyncio
async def test_get_user_unauthenticated(client: AsyncClient, authorized_user):
    """
    Test GET /v1/users/{user_id} without authentication.
    Should hit user_controller.get_user
    """
    _, user_info, _ = authorized_user
    # Fix: key is 'user_id', not 'id'
    user_id = user_info.get("user_id") or user_info.get("id")

    unauth_client = client

    res = await unauth_client.get(f"/v1/users/{user_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "QUERY_SUCCESS"
    assert "user" in data["data"]


@pytest.mark.asyncio
async def test_get_user_authenticated_other(client: AsyncClient, authorized_user, fake):
    """
    Test GET /v1/users/{user_id} with authentication for ANOTHER user.
    Should hit user_controller.get_user_info
    """
    cli, my_info, _ = authorized_user

    # 1. Create a second user WITHOUT logging in as them.
    user2_email = fake.email()
    user2_payload = {
        "email": user2_email,
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + "99",
    }

    # Use the unauth client (or just 'client' fixture? authorized_user consumes it...)
    # authorized_user returns (client, ...). This client has cookies.
    # We want to create user 2 using unauthenticated request?
    # Actually POST /v1/users/ is public. We can use `cli`?
    # No, if we use `cli` (authenticated), it might send cookies, but that shouldn't break signup.
    # Let's try creating with `cli`.

    res = await cli.post("/v1/users/", data=user2_payload)
    if res.status_code == 400 or res.status_code == 403:
        # In case logged in users can't sign up (unlikely for this app)
        # Using a fresh client would be safer but 'client' fixture is one per test.
        # So let's construct a new httpx client if needed or just use `cli`.
        pass
    assert res.status_code == 201

    # 2. Get ID of new user from DB
    from database.connection import get_connection

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM user WHERE email = %s", (user2_email,))
            row = await cur.fetchone()
            other_id = row[0]

    # 3. Request other user's profile with authenticated client
    res_get = await cli.get(f"/v1/users/{other_id}")
    assert res_get.status_code == 200
    assert res_get.json()["code"] == "QUERY_SUCCESS"
    # 타 사용자 프로필에서는 이메일 비공개
    assert "email" not in res_get.json()["data"]["user"]
    assert "nickname" in res_get.json()["data"]["user"]


@pytest.mark.asyncio
async def test_get_user_invalid_id(client: AsyncClient):
    """
    Test GET /v1/users/{user_id} with invalid ID.
    Should raise HTTP 400 from user_controller.get_user
    """
    res = await client.get("/v1/users/0")
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "invalid_user_id"


@pytest.mark.asyncio
async def test_upload_profile_image_endpoint(client: AsyncClient, authorized_user):
    """
    Test POST /v1/users/profile/image
    """
    cli, _, _ = authorized_user
    files = {"file": ("test.jpg", b"fake content", "image/jpeg")}

    # Patch save_uploaded_file to return a fake URL, bypassing storage validation
    with patch("controllers.user_controller.save_file", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = "/uploads/test.jpg"

        res = await cli.post("/v1/users/profile/image", files=files)

        assert res.status_code == 201
        assert res.json()["code"] == "IMAGE_UPLOADED"
        assert res.json()["data"]["url"] == "/uploads/test.jpg"


@pytest.mark.asyncio
async def test_token_expiration(client: AsyncClient, authorized_user):
    """
    Test that expired JWT access tokens are denied with 401.
    """
    from httpx import ASGITransport
    from main import app
    import jwt
    from datetime import datetime, timedelta, timezone

    cli, user_info, _ = authorized_user

    user_id = user_info.get("user_id") or user_info.get("id")

    # 1. 만료된 Access Token 생성
    from core.config import settings

    expired_payload = {
        "sub": str(user_id),
        "email": "test@example.com",
        "nickname": "testuser",
        "role": "user",
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        "type": "access",
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm="HS256")

    # 2. 만료된 토큰으로 보호된 엔드포인트 접근 시도
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {expired_token}"},
    ) as expired_client:
        res = await expired_client.get("/v1/users/me")
        assert res.status_code == 401
        assert res.json()["detail"]["error"] == "token_expired"


@pytest.mark.asyncio
async def test_validation_handler_binary_sanitization():
    """
    Unit test for request_validation_exception_handler to verify binary data sanitization.
    """
    from middleware.exception_handler import request_validation_exception_handler
    from fastapi import Request
    import json

    # Mock Request
    scope = {"type": "http"}
    request = Request(scope)

    # Construct a raw error list mimicking Pydantic structure with bytes
    raw_errors = [
        {
            "type": "value_error",
            "loc": ("body", "file"),
            "msg": "Invalid file",
            "input": b"\x00\x01\x02",  # Binary data in input
            "ctx": {"limit": b"\xff\xff"},  # Binary data in ctx
        }
    ]

    # Create the exception (we can't easily instantiate RequestValidationError directly with raw list
    # because it expects a sequence of ErrorWrapper or similar in older pydantic/fastapi versions,
    # but in Pydantic v2 it wraps a validation error.
    # Actually FastAPI RequestValidationError just takes `errors` list or a validation error.
    # In FastAPI >= 0.100 it takes `errors` (sequence of Any) or `body`.

    # Let's inspect the handler signature. It takes `exc: RequestValidationError`.
    # We can assume we can pass a mock or subclass.

    class MockValidationError:
        def errors(self):
            return raw_errors

    exc = MockValidationError()  # Duck typing

    # Call handler
    response = await request_validation_exception_handler(request, exc)

    # Verify response
    assert response.status_code == 422
    body = json.loads(response.body)

    # Check if binary data was replaced
    detail = body["detail"]
    assert detail[0]["input"] == "<binary data: 3 bytes>"
    assert detail[0]["ctx"]["limit"] == "<binary data: 2 bytes>"


@pytest.mark.asyncio
async def test_create_user_image_upload_fail_http(client: AsyncClient, user_payload):
    """
    Test create_user with image upload failing with HTTPException
    """
    from fastapi import HTTPException

    files = {"profile_image": ("test.jpg", b"fake data", "image/jpeg")}

    with patch("controllers.user_controller.save_file", new_callable=AsyncMock) as mock_save:
        mock_save.side_effect = HTTPException(
            status_code=400, detail={"error": "too_large"}
        )

        # We need to send multipart/form-data.
        # user_payload is dict.
        data = {k: v for k, v in user_payload.items()}

        res = await client.post("/v1/users/", data=data, files=files)

        assert res.status_code == 400
        assert res.json()["detail"]["error"] == "too_large"


@pytest.mark.asyncio
async def test_create_user_image_upload_fail_generic(client: AsyncClient, user_payload):
    """
    Test create_user with image upload failing with generic Exception
    """
    files = {"profile_image": ("test.jpg", b"fake data", "image/jpeg")}

    with patch("controllers.user_controller.save_file", new_callable=AsyncMock) as mock_save:
        mock_save.side_effect = Exception("Storage Error")

        data = {k: v for k, v in user_payload.items()}

        res = await client.post("/v1/users/", data=data, files=files)

        assert res.status_code == 500
        assert res.json()["detail"]["error"] == "image_upload_failed"
        assert "Storage Error" in res.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_upload_profile_image_fail(client: AsyncClient, authorized_user):
    """
    Test upload_profile_image with failure
    """
    cli, _, _ = authorized_user
    files = {"file": ("test.jpg", b"fake image data", "image/jpeg")}

    with patch("controllers.user_controller.save_file", new_callable=AsyncMock) as mock_save:
        # Simulate HTTPException (e.g. file too large)
        mock_save.side_effect = HTTPException(
            status_code=413, detail={"error": "file_too_large"}
        )

        res = await cli.post("/v1/users/profile/image", files=files)
        assert res.status_code == 413
        assert res.json()["detail"]["error"] == "file_too_large"


# ==========================================
# Helpers for test_get_user_authenticated_other
# ==========================================


@pytest.mark.asyncio
async def test_get_other_user_info(client: AsyncClient, authorized_user, fake):
    """
    Specific test for authenticated user viewing ANOTHER user's profile.
    """
    cli, my_info, _ = authorized_user

    # 1. Create a second user WITHOUT logging in as them.
    # We use a fresh client for this setup to avoid messing with `cli` cookies
    # BUT `client` fixture is session/function scoped.
    # We can manually create a user using the DB directly or use a fresh request.

    user2_email = fake.email()
    user2_payload = {
        "email": user2_email,
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + "99",
    }

    # Using the same `cli` would logout the current user if we post to login.
    # But signup (POST /users/) does NOT login automatically in this API (usually).
    # Let's check user_controller.create_user -> returns "SIGNUP_SUCCESS"
    # It does NOT set cookie. Login is separate.
    # So we can safely use `cli` to create user 2.

    res = await cli.post("/v1/users/", data=user2_payload)
    assert res.status_code == 201

    # We need the ID of the new user.
    # Since API doesn't return it, and we don't want to wire up direct DB access in this test file
    # for simplicity, let's guess it.
    # If `my_info` is ID 1, new user is ID 2.
    # But to be safe, let's select from DB if possible, or just guess logic.
    # Or strict way:
    from database.connection import get_connection

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM user WHERE email = %s", (user2_email,))
            row = await cur.fetchone()
            other_id = row[0]

    # Now use `cli` (authenticated as User 1) to view User 2
    res_get = await cli.get(f"/v1/users/{other_id}")
    assert res_get.status_code == 200
    # 타 사용자 프로필에서는 이메일 비공개
    assert "email" not in res_get.json()["data"]["user"]
    assert "nickname" in res_get.json()["data"]["user"]
