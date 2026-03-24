"""소셜 로그인 기능 테스트."""

import pytest
from httpx import AsyncClient

from modules.auth import social_account_models
from modules.user import models as user_models
from tests.conftest import create_verified_user


@pytest.mark.asyncio
async def test_generate_temp_nickname():
    """임시 닉네임이 올바른 형식으로 생성된다."""
    nick = user_models.generate_temp_nickname()
    assert nick.startswith("tmp_")
    assert len(nick) == 10  # "tmp_" + 6 chars


@pytest.mark.asyncio
async def test_add_social_user(client: AsyncClient):
    """소셜 사용자가 password=NULL, nickname_set=0으로 생성된다."""
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email=f"social_{nickname}@test.com",
        nickname=nickname,
    )
    assert user.id > 0
    assert user.password is None
    assert user.nickname_set is False
    assert user.email_verified  # 소셜 사용자는 이메일 인증 완료


@pytest.mark.asyncio
async def test_social_account_crud(client: AsyncClient):
    """소셜 계정 CRUD가 정상 동작한다."""
    # 사용자 생성
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email=f"crud_{nickname}@test.com",
        nickname=nickname,
    )

    # 소셜 계정 생성
    sa_id = await social_account_models.create(
        user_id=user.id,
        provider="github",
        provider_id="github_12345",
        provider_email=f"crud_{nickname}@test.com",
    )
    assert sa_id > 0

    # provider로 조회
    sa = await social_account_models.get_by_provider("github", "github_12345")
    assert sa is not None
    assert sa["user_id"] == user.id
    assert sa["provider"] == "github"

    # user_id로 조회
    accounts = await social_account_models.get_by_user_id(user.id)
    assert len(accounts) == 1
    assert accounts[0]["provider"] == "github"


@pytest.mark.asyncio
async def test_complete_signup_sets_nickname(client: AsyncClient, fake):
    """complete-signup이 닉네임을 설정하고 nickname_set=1로 변경한다."""
    from core.utils.jwt_utils import create_access_token

    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email=f"complete_{nickname}@test.com",
        nickname=nickname,
    )
    token = create_access_token(user_id=user.id)

    # 닉네임 설정
    new_nickname = fake.lexify(text="?????") + str(fake.random_int(10, 99))
    res = await client.post(
        "/v1/auth/social/complete-signup",
        json={"nickname": new_nickname},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["code"] == "SIGNUP_COMPLETED"

    # DB 확인
    updated_user = await user_models.get_user_by_id(user.id)
    assert updated_user.nickname == new_nickname
    assert updated_user.nickname_set is True


@pytest.mark.asyncio
async def test_complete_signup_duplicate_nickname(client: AsyncClient, fake):
    """이미 사용 중인 닉네임으로 complete-signup하면 NICKNAME_DUPLICATED를 반환한다."""
    from core.utils.jwt_utils import create_access_token

    # 기존 사용자 (닉네임 점유)
    existing = await create_verified_user(client, fake)

    # 소셜 사용자
    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email=f"dup_{nickname}@test.com",
        nickname=nickname,
    )
    token = create_access_token(user_id=user.id)

    # 기존 사용자의 닉네임으로 설정 시도
    res = await client.post(
        "/v1/auth/social/complete-signup",
        json={"nickname": existing["nickname"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["code"] == "NICKNAME_DUPLICATED"


@pytest.mark.asyncio
async def test_complete_signup_invalid_nickname(client: AsyncClient):
    """닉네임 규칙 위반 시 422를 반환한다."""
    from core.utils.jwt_utils import create_access_token

    nickname = user_models.generate_temp_nickname()
    user = await user_models.add_social_user(
        email=f"invalid_{nickname}@test.com",
        nickname=nickname,
    )
    token = create_access_token(user_id=user.id)

    # 2자 닉네임 (최소 3자)
    res = await client.post(
        "/v1/auth/social/complete-signup",
        json={"nickname": "ab"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
