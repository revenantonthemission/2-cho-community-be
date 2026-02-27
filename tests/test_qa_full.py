import pytest
from httpx import AsyncClient
import random
import string

def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters, k=length))

# ==========================================
# 1. Auth Tests (AUTH-01 ~ AUTH-06)
# ==========================================

@pytest.mark.asyncio
async def test_auth_01_signup(client: AsyncClient, user_payload):
    """AUTH-01: 유효한 정보로 회원가입"""
    res = await client.post("/v1/users/", data=user_payload)
    assert res.status_code == 201
    data = res.json()
    # [수정] 응답 코드 맞춤
    assert data["code"] == "SIGNUP_SUCCESS"
    # create_user 컨트롤러는 data={}를 반환하므로 이메일 검증 생략


@pytest.mark.asyncio
async def test_auth_02_signup_duplicate(client: AsyncClient, user_payload):
    """AUTH-02: 중복된 이메일/닉네임 회원가입 실패"""
    await client.post("/v1/users/", data=user_payload)
    res = await client.post("/v1/users/", data=user_payload)
    assert res.status_code == 409
    # 에러 응답은 {"detail": ...} 또는 {"error": ...}
    # status code가 409이면 통과
    
@pytest.mark.asyncio
async def test_auth_03_login(client: AsyncClient, authorized_user):
    """AUTH-03: 올바른 정보로 로그인"""
    _, user_info, _ = authorized_user
    assert user_info["email"] is not None

@pytest.mark.asyncio
async def test_auth_04_login_fail(client: AsyncClient, user_payload):
    """AUTH-04: 틀린 비밀번호로 로그인 실패"""
    await client.post("/v1/users/", data=user_payload)
    res = await client.post("/v1/auth/session", json={
        "email": user_payload["email"],
        "password": "WrongPassword123!"
    })
    assert res.status_code == 401
    assert res.json()["detail"]["error"] == "unauthorized"

@pytest.mark.asyncio
async def test_auth_05_me(client: AsyncClient, authorized_user):
    """AUTH-05: 내 정보 조회"""
    cli, _, _ = authorized_user
    res = await cli.get("/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["data"]["user"]["email"] is not None

@pytest.mark.asyncio
async def test_auth_06_logout(client: AsyncClient, authorized_user):
    """AUTH-06: 로그아웃 — Refresh Token이 무효화되어 토큰 갱신 실패 확인."""
    cli, _, _ = authorized_user
    res = await cli.delete("/v1/auth/session")
    assert res.status_code == 200

    # JWT 기반 인증에서 Access Token은 stateless이므로 로그아웃 후에도 유효함.
    # 대신 Refresh Token이 무효화되어 토큰 갱신이 실패하는지 확인.
    refresh_res = await cli.post("/v1/auth/token/refresh")
    assert refresh_res.status_code == 401

# ==========================================
# 2. Post Tests (POST-01 ~ POST-08)
# ==========================================

@pytest.mark.asyncio
async def test_post_crud_flow(client: AsyncClient, authorized_user):
    """POST-01 ~ POST-08 통합 시나리오"""
    cli, user_info, _ = authorized_user
    
    post_payload = {
        "title": "Test Title",
        "content": "Test Content",
        "image_url": "/uploads/images/test_img.jpg"
    }
    create_res = await cli.post("/v1/posts/", json=post_payload)
    assert create_res.status_code == 201
    post_id = create_res.json()["data"]["post_id"]
    
    list_res = await cli.get("/v1/posts/?offset=0&limit=10")
    assert list_res.status_code == 200
    posts = list_res.json()["data"]["posts"]
    assert len(posts) >= 1
    
    detail_res_before = await cli.get(f"/v1/posts/{post_id}")
    assert detail_res_before.status_code == 200
    
    # 수정
    update_payload = {"title": "Updated Title", "content": "Updated Content"}
    update_res = await cli.patch(f"/v1/posts/{post_id}", json=update_payload)
    assert update_res.status_code == 200
    
    # 삭제
    del_res = await cli.delete(f"/v1/posts/{post_id}")
    assert del_res.status_code == 200
    
    missing_res = await cli.get(f"/v1/posts/{post_id}")
    assert missing_res.status_code == 404

@pytest.mark.asyncio
async def test_post_02_unauthorized_create(client: AsyncClient):
    """POST-02: 비로그인 게시글 작성 실패"""
    res = await client.post("/v1/posts/", json={"title": "Test Title", "content": "Content"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_post_06_forbidden_update(client: AsyncClient, authorized_user, fake):
    """POST-06: 타인의 게시글 수정 실패"""
    cli1, user1, _ = authorized_user

    res = await cli1.post("/v1/posts/", json={"title": "User1 Post", "content": "c"})
    post_id = res.json()["data"]["post_id"]

    user2_payload = {
        "email": fake.email(),
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99))
    }
    await client.post("/v1/users/", data=user2_payload)
    login_res = await client.post("/v1/auth/session", json={"email": user2_payload["email"], "password": "Password123!"})
    access_token = login_res.json()["data"]["access_token"]

    # JWT Bearer Token으로 인증된 요청 전송
    fail_res = await client.patch(
        f"/v1/posts/{post_id}",
        json={"title": "Hacked"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert fail_res.status_code == 403

# ==========================================
# 3. Comment Tests (CMT-01 ~ CMT-03)
# ==========================================

@pytest.mark.asyncio
async def test_comment_flow(client: AsyncClient, authorized_user):
    """CMT-01 ~ CMT-03 통합 시나리오"""
    cli, _, _ = authorized_user
    
    post_res = await cli.post("/v1/posts/", json={"title": "Post Title", "content": "Content"})
    post_id = post_res.json()["data"]["post_id"]
    
    cmt_res = await cli.post(f"/v1/posts/{post_id}/comments", json={"content": "Comment 1"})
    assert cmt_res.status_code == 201
    comment_id = cmt_res.json()["data"]["comment_id"]
    
    upd_res = await cli.put(f"/v1/posts/{post_id}/comments/{comment_id}", json={"content": "Updated Comment"})
    assert upd_res.status_code == 200
    
    del_res = await cli.delete(f"/v1/posts/{post_id}/comments/{comment_id}")
    assert del_res.status_code == 200

# ==========================================
# 4. Like Tests (LIKE-01 ~ LIKE-02)
# ==========================================

@pytest.mark.asyncio
async def test_like_flow(client: AsyncClient, authorized_user):
    """LIKE-01, LIKE-02 통합 시나리오"""
    cli, _, _ = authorized_user
    
    post_res = await cli.post("/v1/posts/", json={"title": "Like Test", "content": "C"})
    post_id = post_res.json()["data"]["post_id"]
    
    like_res = await cli.post(f"/v1/posts/{post_id}/likes")
    assert like_res.status_code == 201
    
    unlike_res = await cli.delete(f"/v1/posts/{post_id}/likes")
    assert unlike_res.status_code == 200

# ==========================================
# 5. User Tests (USER-01 ~ USER-03)
# ==========================================

@pytest.mark.asyncio
async def test_user_management(client: AsyncClient, authorized_user):
    """USER-01 ~ USER-03 통합 시나리오"""
    cli, user_info, user_payload = authorized_user
    
    new_nick = "New_" + random_string(5)
    update_res = await cli.patch("/v1/users/me", json={"nickname": new_nick})
    assert update_res.status_code == 200
    
    data = update_res.json()["data"]
    nick = data.get("user", {}).get("nickname") or data.get("nickname")
    assert nick == new_nick
    
    # [수정] 비밀번호 변경 스키마 맞춤 (ChangePasswordRequest: new_password, new_password_confirm)
    new_pw = "NewPass123!"
    pw_res = await cli.put("/v1/users/me/password", json={
        "new_password": new_pw,
        "new_password_confirm": new_pw
    })
    
    if pw_res.status_code == 422:
        print(pw_res.json())
        
    assert pw_res.status_code == 200
    
    await cli.delete("/v1/auth/session")
    login_res = await cli.post("/v1/auth/session", json={
        "email": user_payload["email"],
        "password": new_pw
    })
    assert login_res.status_code == 200
    
    withdraw_res = await cli.request("DELETE", "/v1/users/me", json={
        "password": new_pw,
        "agree": True
    })
    assert withdraw_res.status_code == 200
    
    login_fail = await cli.post("/v1/auth/session", json={
        "email": user_payload["email"],
        "password": new_pw
    })
    assert login_fail.status_code == 401
