"""Users 도메인 — 회원가입 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import _make_user_payload

# ---------------------------------------------------------------------------
# 회원가입 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_with_valid_data_returns_201(client: AsyncClient, fake):
    """유효한 Form 데이터로 회원가입 시 201을 반환한다."""
    # Arrange
    payload = _make_user_payload(fake)

    # Act
    res = await client.post("/v1/users/", data=payload)

    # Assert
    assert res.status_code == 201
    body = res.json()
    assert body["code"] == "SIGNUP_SUCCESS"


# ---------------------------------------------------------------------------
# 회원가입 실패 — 중복
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_with_duplicate_email_returns_409(client: AsyncClient, fake):
    """이미 가입된 이메일로 회원가입 시 409를 반환한다."""
    # Arrange — 첫 번째 가입
    payload = _make_user_payload(fake)
    res1 = await client.post("/v1/users/", data=payload)
    assert res1.status_code == 201

    # Act — 같은 이메일, 다른 닉네임으로 재가입
    second_payload = {**payload, "nickname": fake.lexify(text="?????") + "99"}
    res2 = await client.post("/v1/users/", data=second_payload)

    # Assert
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_signup_with_duplicate_nickname_returns_409(client: AsyncClient, fake):
    """이미 사용 중인 닉네임으로 회원가입 시 409를 반환한다."""
    # Arrange — 첫 번째 가입
    payload = _make_user_payload(fake)
    res1 = await client.post("/v1/users/", data=payload)
    assert res1.status_code == 201

    # Act — 같은 닉네임, 다른 이메일로 재가입
    second_payload = {**payload, "email": fake.email()}
    res2 = await client.post("/v1/users/", data=second_payload)

    # Assert
    assert res2.status_code == 409


# ---------------------------------------------------------------------------
# 회원가입 실패 — 유효성 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signup_with_invalid_email_format_returns_422(client: AsyncClient, fake):
    """잘못된 이메일 형식으로 회원가입 시 400을 반환한다."""
    payload = _make_user_payload(fake, email="not-an-email")

    res = await client.post("/v1/users/", data=payload)

    # CreateUserRequest 유효성 검증 실패 → 400 (라우터에서 ValidationError 처리)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_signup_with_short_password_returns_422(client: AsyncClient, fake):
    """짧은 비밀번호로 회원가입 시 400을 반환한다."""
    payload = _make_user_payload(fake, password="Ab1!")

    res = await client.post("/v1/users/", data=payload)

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_signup_with_long_nickname_returns_422(client: AsyncClient, fake):
    """10자를 초과하는 닉네임으로 회원가입 시 400을 반환한다."""
    payload = _make_user_payload(fake, nickname="a" * 11)

    res = await client.post("/v1/users/", data=payload)

    assert res.status_code == 400
