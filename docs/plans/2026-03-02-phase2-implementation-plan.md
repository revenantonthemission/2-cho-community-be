# Phase 2: 사용자 활동 & 알림 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 내 활동 페이지, 알림 시스템, 이메일 인증, 타 사용자 프로필 4개 기능을 추가한다.

**Architecture:** 기존 FastAPI(Router→Controller→Model) + Vanilla JS MVC 패턴 유지. 알림은 폴링(30초), 이메일 인증은 SHA-256 토큰, 내 활동은 기존 테이블 WHERE 조건.

**Tech Stack:** FastAPI, aiomysql, Pydantic, Vanilla JS ES6 Modules, MySQL

**Design Doc:** `docs/plans/2026-03-02-phase2-user-activity-notifications-design.md`

---

## Task 1: DB 스키마 + User 모델 + 테스트 인프라

이 태스크는 Phase 2 전체의 기반이 되는 DB 변경, User 데이터클래스 수정, 테스트 픽스처 업데이트를 수행합니다.

**Files:**
- Modify: `database/schema.sql`
- Modify: `models/user_models.py`
- Modify: `schemas/common.py`
- Modify: `controllers/auth_controller.py`
- Modify: `tests/conftest.py`

### Step 1: schema.sql에 email_verified 컬럼 및 신규 테이블 추가

`database/schema.sql` 수정:

1. `user` 테이블에 `email_verified` 컬럼 추가 (`email` 뒤):

```sql
CREATE TABLE user (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    email_verified TINYINT(1) NOT NULL DEFAULT 0,
    nickname varchar(255) NOT NULL UNIQUE,
    password varchar(2048) NOT NULL,
    profile_img varchar(2048) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);
```

2. `refresh_token` 테이블 뒤에 `email_verification` 테이블 추가:

```sql
-- 이메일 인증 토큰 테이블
CREATE TABLE email_verification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);
```

3. `post_view_log` 테이블 뒤에 `notification` 테이블 추가:

```sql
-- 알림 테이블
CREATE TABLE notification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    type ENUM('comment', 'like') NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    comment_id INT UNSIGNED NULL,
    actor_id INT UNSIGNED NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES user (id) ON DELETE CASCADE
);
```

4. 인덱스 섹션에 추가:

```sql
    -- 8. 이메일 인증 토큰 조회
    CREATE INDEX idx_email_verification_token ON email_verification (token_hash);
    CREATE INDEX idx_email_verification_expires ON email_verification (expires_at);

    -- 9. 알림 목록 조회 (사용자별 + 읽음 상태 + 최신순)
    CREATE INDEX idx_notification_user_unread ON notification (user_id, is_read, created_at DESC);

    -- 10. 내 활동: 댓글 작성자별 조회
    CREATE INDEX idx_comment_author ON comment (author_id, created_at DESC);

    -- 11. 내 활동: 좋아요 사용자별 조회
    CREATE INDEX idx_post_like_user ON post_like (user_id, created_at DESC);
```

### Step 2: User 데이터클래스에 email_verified 필드 추가

`models/user_models.py` 수정:

1. `User` 데이터클래스 (line 18-40)에 `email_verified` 필드 추가:

```python
@dataclass(frozen=True)
class User:
    id: int
    email: str
    email_verified: bool = False
    password: str = ""
    nickname: str = ""
    profile_image_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
```

2. `USER_SELECT_FIELDS` (line 55-57) 수정:

```python
USER_SELECT_FIELDS = (
    "id, email, email_verified, nickname, password, profile_img, "
    "created_at, updated_at, deleted_at"
)
```

3. `_row_to_user` (line 60-78) 수정 — 인덱스가 1개씩 밀림:

```python
def _row_to_user(row: tuple) -> User:
    return User(
        id=row[0],
        email=row[1],
        email_verified=bool(row[2]),
        nickname=row[3],
        password=row[4],
        profile_image_url=row[5],
        created_at=row[6],
        updated_at=row[7],
        deleted_at=row[8],
    )
```

### Step 3: serialize_user에 email_verified 추가

`schemas/common.py`의 `serialize_user()` (line 59-73) 수정:

```python
def serialize_user(user) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "email": user.email,
        "email_verified": user.email_verified,
        "nickname": user.nickname,
        "profileImageUrl": user.profileImageUrl,
    }
```

이 변경으로 `GET /v1/auth/me`, 로그인 응답 등에 `email_verified` 필드가 자동으로 포함됩니다.

### Step 4: conftest.py 업데이트

`tests/conftest.py` 수정:

1. `clear_all_data()` (line 15-26)에 신규 테이블 추가:

```python
async def clear_all_data() -> None:
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            await cur.execute("TRUNCATE TABLE notification")
            await cur.execute("TRUNCATE TABLE email_verification")
            await cur.execute("TRUNCATE TABLE post_view_log")
            await cur.execute("TRUNCATE TABLE post_like")
            await cur.execute("TRUNCATE TABLE comment")
            await cur.execute("TRUNCATE TABLE post")
            await cur.execute("TRUNCATE TABLE refresh_token")
            await cur.execute("TRUNCATE TABLE user")
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")
```

2. `authorized_user` 픽스처 (line 67-102)에서 회원가입 후 `email_verified = 1` 설정 추가:

```python
@pytest_asyncio.fixture
async def authorized_user(client, user_payload):
    signup_res = await client.post("/v1/users/", data=user_payload)
    if signup_res.status_code != 201:
        print(f"Signup failed: {signup_res.status_code}, {signup_res.text}")
    assert signup_res.status_code == 201

    # 이메일 인증 완료 처리 (기존 테스트가 쓰기 기능을 사용할 수 있도록)
    user_id = signup_res.json()["data"]["user_id"]
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE id = %s", (user_id,)
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res.status_code == 200

    login_data = login_res.json()
    access_token = login_data["data"]["access_token"]
    user_info = login_data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    async with auth_client as ac:
        yield ac, user_info, user_payload
```

3. 미인증 사용자 픽스처 추가 (파일 끝):

```python
@pytest_asyncio.fixture
async def unverified_user(client, user_payload):
    """이메일 미인증 상태의 로그인된 클라이언트를 반환합니다."""
    signup_res = await client.post("/v1/users/", data=user_payload)
    assert signup_res.status_code == 201

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res.status_code == 200

    login_data = login_res.json()
    access_token = login_data["data"]["access_token"]
    user_info = login_data["data"]["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    async with auth_client as ac:
        yield ac, user_info, user_payload
```

### Step 5: DB 스키마 재로드 및 기존 테스트 실행

```bash
cd 2-cho-community-be
mysql -u root -p community_service < database/schema.sql
pytest -x -v
```

모든 기존 테스트가 통과해야 합니다.

### Step 6: 커밋

```bash
git add database/schema.sql models/user_models.py schemas/common.py tests/conftest.py
git commit -m "feat: Phase 2 DB schema + User model email_verified + test fixtures"
```

---

## Task 2: 이메일 인증 백엔드

이메일 인증 토큰 생성, 검증, 재발송 기능을 구현합니다.

**Files:**
- Create: `models/verification_models.py`
- Create: `tests/test_email_verification.py`
- Modify: `controllers/auth_controller.py`
- Modify: `routers/auth_router.py`
- Modify: `services/user_service.py` (회원가입 시 인증 메일 발송)
- Modify: `main.py` (만료 토큰 정리에 email_verification 추가)

### Step 1: 이메일 인증 테스트 작성

`tests/test_email_verification.py` 생성:

```python
"""이메일 인증 기능 테스트."""

import hashlib

import pytest


@pytest.mark.asyncio
async def test_signup_returns_unverified_user(client, user_payload):
    """회원가입 후 email_verified가 False입니다."""
    res = await client.post("/v1/users/", data=user_payload)
    assert res.status_code == 201

    # 로그인
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res.json()["data"]["user"]["email_verified"] is False


@pytest.mark.asyncio
async def test_verify_email_success(client, user_payload):
    """유효한 토큰으로 이메일 인증에 성공합니다."""
    from database.connection import get_connection

    res = await client.post("/v1/users/", data=user_payload)
    assert res.status_code == 201

    # DB에서 토큰 해시 조회 → 역산 불가하므로 테스트에서는 직접 토큰 생성
    # 대신 resend API를 통해 테스트
    # 로그인 후 resend 호출 → DB에서 해시 확인 → verify 호출
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    access_token = login_res.json()["data"]["access_token"]

    # 인증 메일 재발송 (토큰 생성)
    headers = {"Authorization": f"Bearer {access_token}"}
    resend_res = await client.post("/v1/auth/resend-verification", headers=headers)
    assert resend_res.status_code == 200

    # DB에서 raw token 대신 hash를 가져와서 역으로 검증할 수 없음
    # 테스트용: DB에서 token_hash를 읽고, 모델의 verify 함수를 직접 호출
    from models import verification_models

    user_id = res.json()["data"]["user_id"]
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT token_hash FROM email_verification WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
    assert row is not None

    # verify_email API는 raw token이 필요하지만 DB에는 hash만 저장됨
    # 테스트를 위해 모델 레벨에서 직접 토큰을 생성하고 검증
    import secrets

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # 기존 토큰 교체
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE email_verification SET token_hash = %s WHERE user_id = %s",
                (token_hash, user_id),
            )

    # 인증 API 호출
    verify_res = await client.post(
        "/v1/auth/verify-email", json={"token": raw_token}
    )
    assert verify_res.status_code == 200

    # 로그인하여 email_verified 확인
    login_res2 = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res2.json()["data"]["user"]["email_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client, user_payload):
    """유효하지 않은 토큰은 400 에러를 반환합니다."""
    await client.post("/v1/users/", data=user_payload)

    res = await client.post(
        "/v1/auth/verify-email", json={"token": "invalid_token_abc"}
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_already_verified(authorized_user):
    """이미 인증된 사용자는 재발송 시 400 에러를 반환합니다."""
    client, _, _ = authorized_user
    res = await client.post("/v1/auth/resend-verification")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_unauthenticated(client):
    """미로그인 사용자는 재발송 시 401 에러를 반환합니다."""
    res = await client.post("/v1/auth/resend-verification")
    assert res.status_code == 401
```

### Step 2: 테스트 실행 — 실패 확인

```bash
pytest tests/test_email_verification.py -v
```

Expected: FAIL (endpoint 미구현)

### Step 3: verification_models.py 구현

`models/verification_models.py` 생성:

```python
"""verification_models: 이메일 인증 토큰 관련 모델.

Refresh Token과 동일한 SHA-256 해시 패턴을 사용합니다.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from database.connection import get_connection, transactional

_TOKEN_EXPIRE_HOURS = 24


def _hash_token(raw_token: str) -> str:
    """토큰을 SHA-256 해시로 변환합니다."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_verification_token(user_id: int) -> str:
    """이메일 인증 토큰을 생성합니다.

    기존 토큰이 있으면 교체(REPLACE)합니다.

    Returns:
        raw token (메일로 발송할 원본 토큰).
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS)

    async with transactional() as cur:
        # user_id UNIQUE이므로 REPLACE로 기존 토큰 교체
        await cur.execute(
            """
            REPLACE INTO email_verification (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )

    return raw_token


async def verify_token(raw_token: str) -> int | None:
    """토큰을 검증하고 user_id를 반환합니다.

    성공 시 email_verification 행을 삭제하고 user.email_verified를 1로 설정합니다.

    Returns:
        user_id (성공 시) 또는 None (실패 시).
    """
    token_hash = _hash_token(raw_token)

    async with transactional() as cur:
        await cur.execute(
            """
            SELECT user_id, expires_at
            FROM email_verification
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = await cur.fetchone()

        if not row:
            return None

        user_id, expires_at = row[0], row[1]

        # 만료 확인
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            await cur.execute(
                "DELETE FROM email_verification WHERE token_hash = %s",
                (token_hash,),
            )
            return None

        # 인증 완료: 토큰 삭제 + 사용자 상태 업데이트
        await cur.execute(
            "DELETE FROM email_verification WHERE token_hash = %s",
            (token_hash,),
        )
        await cur.execute(
            "UPDATE user SET email_verified = 1 WHERE id = %s",
            (user_id,),
        )

    return user_id


async def is_user_verified(user_id: int) -> bool:
    """사용자의 이메일 인증 여부를 확인합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT email_verified FROM user WHERE id = %s AND deleted_at IS NULL",
                (user_id,),
            )
            row = await cur.fetchone()
            return bool(row[0]) if row else False


async def cleanup_expired_verification_tokens() -> int:
    """만료된 이메일 인증 토큰을 일괄 삭제합니다.

    Returns:
        삭제된 행 수.
    """
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM email_verification WHERE expires_at < NOW()"
        )
        return cur.rowcount
```

### Step 4: auth_controller.py에 verify_email, resend_verification 추가

`controllers/auth_controller.py` 끝에 추가:

```python
async def verify_email(token: str, request: Request) -> dict:
    """이메일 인증 토큰을 검증합니다."""
    timestamp = get_request_timestamp(request)

    from models import verification_models

    user_id = await verification_models.verify_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_or_expired_token", "timestamp": timestamp},
        )

    return create_response(
        "EMAIL_VERIFIED",
        "이메일 인증이 완료되었습니다.",
        timestamp=timestamp,
    )


async def resend_verification(current_user: User, request: Request) -> dict:
    """이메일 인증 메일을 재발송합니다."""
    timestamp = get_request_timestamp(request)

    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "already_verified", "timestamp": timestamp},
        )

    from models import verification_models
    from utils.email import send_email
    from core.config import settings

    raw_token = await verification_models.create_verification_token(current_user.id)

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:8080")
    verify_link = f"{frontend_url}/verify-email.html?token={raw_token}"

    try:
        await send_email(
            to=current_user.email,
            subject="[아무 말 대잔치] 이메일 인증",
            body=f"아래 링크를 클릭하여 이메일을 인증하세요:\n\n{verify_link}\n\n이 링크는 24시간 동안 유효합니다.",
        )
    except RuntimeError:
        pass  # 이메일 발송 실패를 노출하지 않음

    return create_response(
        "VERIFICATION_SENT",
        "인증 메일을 발송했습니다.",
        timestamp=timestamp,
    )
```

### Step 5: auth_router.py에 새 엔드포인트 추가

`routers/auth_router.py` 끝에 추가:

```python
from pydantic import BaseModel

class VerifyEmailRequest(BaseModel):
    token: str

@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, request: Request):
    return await auth_controller.verify_email(body.token, request)

@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await auth_controller.resend_verification(current_user, request)
```

**주의**: `VerifyEmailRequest` 스키마는 `schemas/auth_schemas.py`에 추가하는 것이 더 적절합니다. 서브에이전트가 판단하여 배치하세요.

### Step 6: user_service.py 회원가입 시 인증 토큰 생성

`services/user_service.py`의 `create_user` 메서드 끝에서, 사용자 생성 성공 후:

```python
# 이메일 인증 토큰 생성 및 메일 발송
from models import verification_models
from utils.email import send_email

raw_token = await verification_models.create_verification_token(user.id)

frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:8080")
verify_link = f"{frontend_url}/verify-email.html?token={raw_token}"

try:
    await send_email(
        to=user.email,
        subject="[아무 말 대잔치] 이메일 인증",
        body=f"아래 링크를 클릭하여 이메일을 인증하세요:\n\n{verify_link}\n\n이 링크는 24시간 동안 유효합니다.",
    )
except RuntimeError:
    pass  # 이메일 발송 실패가 회원가입을 막지 않음
```

**중요**: 테스트 환경에서 이메일 발송이 실패해도 회원가입은 성공해야 합니다.

### Step 7: main.py 주기적 정리에 email_verification 추가

`main.py`의 `_periodic_token_cleanup()` 함수에 추가:

```python
async def _periodic_token_cleanup() -> None:
    from models.token_models import cleanup_expired_tokens
    from models.verification_models import cleanup_expired_verification_tokens

    while True:
        await asyncio.sleep(_TOKEN_CLEANUP_INTERVAL_HOURS * 3600)
        try:
            await cleanup_expired_tokens()
            await cleanup_expired_verification_tokens()
        except Exception:
            logger.exception("토큰 정리 중 오류 발생")
```

### Step 8: 테스트 실행 — 통과 확인

```bash
pytest tests/test_email_verification.py -v
```

### Step 9: 커밋

```bash
git add models/verification_models.py tests/test_email_verification.py \
    controllers/auth_controller.py routers/auth_router.py \
    services/user_service.py main.py
git commit -m "feat: email verification backend (model, controller, router, tests)"
```

---

## Task 3: 이메일 인증 가드 (require_verified_email)

미인증 사용자의 쓰기 기능을 차단하는 의존성을 추가합니다.

**Files:**
- Modify: `dependencies/auth.py`
- Modify: `routers/post_router.py`
- Create: `tests/test_email_verification_guard.py`

### Step 1: 테스트 작성

`tests/test_email_verification_guard.py` 생성:

```python
"""이메일 미인증 사용자의 쓰기 기능 차단 테스트."""

import pytest


@pytest.mark.asyncio
async def test_unverified_user_cannot_create_post(unverified_user):
    """미인증 사용자는 게시글을 작성할 수 없습니다."""
    client, _, _ = unverified_user
    res = await client.post("/v1/posts/", json={"title": "테스트 글", "content": "내용"})
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


@pytest.mark.asyncio
async def test_unverified_user_cannot_comment(unverified_user, authorized_user):
    """미인증 사용자는 댓글을 작성할 수 없습니다."""
    auth_client, _, _ = authorized_user
    # 인증된 사용자가 게시글 생성
    post_res = await auth_client.post(
        "/v1/posts/", json={"title": "테스트 글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    unverified_client, _, _ = unverified_user
    res = await unverified_client.post(
        f"/v1/posts/{post_id}/comments", json={"content": "댓글"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unverified_user_cannot_like(unverified_user, authorized_user):
    """미인증 사용자는 좋아요를 할 수 없습니다."""
    auth_client, _, _ = authorized_user
    post_res = await auth_client.post(
        "/v1/posts/", json={"title": "테스트 글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    unverified_client, _, _ = unverified_user
    res = await unverified_client.post(f"/v1/posts/{post_id}/likes", json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unverified_user_can_read_posts(unverified_user, authorized_user):
    """미인증 사용자는 게시글 조회는 가능합니다."""
    auth_client, _, _ = authorized_user
    await auth_client.post("/v1/posts/", json={"title": "테스트", "content": "내용"})

    unverified_client, _, _ = unverified_user
    res = await unverified_client.get("/v1/posts/")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_verified_user_can_create_post(authorized_user):
    """인증된 사용자는 게시글을 작성할 수 있습니다."""
    client, _, _ = authorized_user
    res = await client.post("/v1/posts/", json={"title": "테스트 글", "content": "내용"})
    assert res.status_code == 201
```

### Step 2: 테스트 실행 — 실패 확인

```bash
pytest tests/test_email_verification_guard.py -v
```

### Step 3: require_verified_email 의존성 구현

`dependencies/auth.py`에 추가:

```python
async def require_verified_email(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """이메일 인증이 완료된 사용자만 허용합니다.

    미인증 시 403 Forbidden을 발생시킵니다.
    """
    if not current_user.email_verified:
        timestamp = request.state.timestamp if hasattr(request.state, "timestamp") else ""
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "email_not_verified",
                "message": "이메일 인증 후 이용 가능합니다.",
                "timestamp": timestamp,
            },
        )
    return current_user
```

### Step 4: 쓰기 라우트에 require_verified_email 적용

`routers/post_router.py`에서 쓰기 엔드포인트의 `get_current_user`를 `require_verified_email`로 교체:

- `POST /v1/posts/` (게시글 생성)
- `PATCH /v1/posts/{post_id}` (게시글 수정)
- `DELETE /v1/posts/{post_id}` (게시글 삭제)
- `POST /v1/posts/{post_id}/likes` (좋아요)
- `DELETE /v1/posts/{post_id}/likes` (좋아요 취소)
- `POST /v1/posts/{post_id}/comments` (댓글 생성)
- `PUT /v1/posts/{post_id}/comments/{comment_id}` (댓글 수정)
- `DELETE /v1/posts/{post_id}/comments/{comment_id}` (댓글 삭제)

import 추가:

```python
from dependencies.auth import get_current_user, get_optional_user, require_verified_email
```

각 쓰기 라우트의 `Depends(get_current_user)` → `Depends(require_verified_email)` 로 변경.

### Step 5: 테스트 통과 확인 + 기존 테스트 확인

```bash
pytest tests/test_email_verification_guard.py -v
pytest -x -v  # 전체 테스트
```

### Step 6: 커밋

```bash
git add dependencies/auth.py routers/post_router.py tests/test_email_verification_guard.py
git commit -m "feat: require_verified_email guard on write routes"
```

---

## Task 4: 알림 모델 + 테스트

알림 CRUD 모델을 구현합니다.

**Files:**
- Create: `models/notification_models.py`
- Create: `tests/test_notifications.py`

### Step 1: 테스트 작성

`tests/test_notifications.py` 생성:

```python
"""알림 시스템 테스트."""

import pytest


@pytest.mark.asyncio
async def test_create_notification_on_comment(authorized_user, client, user_payload):
    """댓글 작성 시 게시글 작성자에게 알림이 생성됩니다."""
    from faker import Faker

    fake = Faker("ko_KR")
    post_client, post_user, _ = authorized_user

    # 게시글 생성
    post_res = await post_client.post(
        "/v1/posts/", json={"title": "알림 테스트 글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    # 다른 사용자 생성 + 로그인
    other_payload = {
        "email": fake.email(),
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
    }
    await client.post("/v1/users/", data=other_payload)

    # 이메일 인증 처리
    from database.connection import get_connection

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (other_payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": other_payload["email"], "password": other_payload["password"]},
    )
    other_token = login_res.json()["data"]["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # 댓글 작성
    await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "댓글입니다"},
        headers=other_headers,
    )

    # 게시글 작성자의 알림 확인
    notif_res = await post_client.get("/v1/notifications")
    assert notif_res.status_code == 200

    notifications = notif_res.json()["data"]["notifications"]
    assert len(notifications) >= 1
    assert notifications[0]["type"] == "comment"
    assert notifications[0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_no_self_notification(authorized_user):
    """자기 게시글에 자기가 댓글을 달면 알림이 생성되지 않습니다."""
    client, _, _ = authorized_user

    post_res = await client.post(
        "/v1/posts/", json={"title": "내 글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    await client.post(
        f"/v1/posts/{post_id}/comments", json={"content": "내 댓글"}
    )

    notif_res = await client.get("/v1/notifications")
    assert notif_res.status_code == 200
    assert len(notif_res.json()["data"]["notifications"]) == 0


@pytest.mark.asyncio
async def test_unread_count(authorized_user):
    """읽지 않은 알림 수를 조회합니다."""
    client, _, _ = authorized_user

    res = await client.get("/v1/notifications/unread-count")
    assert res.status_code == 200
    assert res.json()["data"]["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_notification_read(authorized_user):
    """알림을 읽음 처리합니다."""
    client, _, _ = authorized_user

    # 알림이 없는 상태에서 존재하지 않는 알림 읽음 처리 시도
    res = await client.patch("/v1/notifications/99999/read")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_mark_all_read(authorized_user):
    """전체 알림을 읽음 처리합니다."""
    client, _, _ = authorized_user

    res = await client.patch("/v1/notifications/read-all")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_delete_notification(authorized_user):
    """알림을 삭제합니다."""
    client, _, _ = authorized_user

    res = await client.delete("/v1/notifications/99999")
    assert res.status_code == 404
```

### Step 2: 테스트 실행 — 실패 확인

```bash
pytest tests/test_notifications.py -v
```

### Step 3: notification_models.py 구현

`models/notification_models.py` 생성:

```python
"""notification_models: 알림 관련 모델."""

from database.connection import get_connection, transactional
from schemas.common import build_author_dict
from utils.formatters import format_datetime


async def create_notification(
    user_id: int,
    notification_type: str,
    post_id: int,
    actor_id: int,
    comment_id: int | None = None,
) -> None:
    """알림을 생성합니다.

    자기 자신에 대한 알림은 생성하지 않습니다.
    """
    if user_id == actor_id:
        return

    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO notification (user_id, type, post_id, comment_id, actor_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, notification_type, post_id, comment_id, actor_id),
        )


async def get_notifications(
    user_id: int, offset: int = 0, limit: int = 20
) -> tuple[list[dict], int]:
    """사용자의 알림 목록과 총 개수를 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # 총 개수
            await cur.execute(
                "SELECT COUNT(*) FROM notification WHERE user_id = %s",
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            # 알림 목록 (actor + post 정보 JOIN)
            await cur.execute(
                """
                SELECT n.id, n.type, n.post_id, n.comment_id, n.is_read, n.created_at,
                       u.id AS actor_id, u.nickname AS actor_nickname,
                       u.profile_img AS actor_profile_img,
                       p.title AS post_title
                FROM notification n
                LEFT JOIN user u ON n.actor_id = u.id
                LEFT JOIN post p ON n.post_id = p.id
                WHERE n.user_id = %s
                ORDER BY n.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    notifications = []
    for row in rows:
        notifications.append({
            "notification_id": row[0],
            "type": row[1],
            "post_id": row[2],
            "comment_id": row[3],
            "is_read": bool(row[4]),
            "created_at": format_datetime(row[5]),
            "actor": build_author_dict(row[6], row[7], row[8]),
            "post_title": row[9] or "삭제된 게시글",
        })

    return notifications, total_count


async def get_unread_count(user_id: int) -> int:
    """읽지 않은 알림 수를 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM notification WHERE user_id = %s AND is_read = 0",
                (user_id,),
            )
            return (await cur.fetchone())[0]


async def mark_as_read(notification_id: int, user_id: int) -> bool:
    """알림을 읽음 처리합니다. 성공 시 True."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE notification SET is_read = 1 WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )
        return cur.rowcount > 0


async def mark_all_as_read(user_id: int) -> int:
    """모든 알림을 읽음 처리합니다. 변경된 행 수를 반환합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE notification SET is_read = 1 WHERE user_id = %s AND is_read = 0",
            (user_id,),
        )
        return cur.rowcount


async def delete_notification(notification_id: int, user_id: int) -> bool:
    """알림을 삭제합니다. 성공 시 True."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM notification WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )
        return cur.rowcount > 0
```

### Step 4: 커밋

```bash
git add models/notification_models.py tests/test_notifications.py
git commit -m "feat: notification model (CRUD + tests)"
```

---

## Task 5: 알림 트리거 + API 라우터

댓글/좋아요 시 알림 생성 트리거와 알림 API 엔드포인트를 구현합니다.

**Files:**
- Modify: `controllers/comment_controller.py`
- Modify: `controllers/like_controller.py`
- Create: `controllers/notification_controller.py`
- Create: `routers/notification_router.py`
- Modify: `main.py` (라우터 등록)

### Step 1: 알림 트리거 — comment_controller.py 수정

`controllers/comment_controller.py`의 `create_comment` 함수에서, `comment = await comment_models.create_comment(...)` 성공 후, `return create_response(...)` 전에 추가:

```python
# 알림 생성 (실패해도 댓글 생성에 영향 없음)
try:
    from models import notification_models

    if comment.parent_id:
        # 대댓글 → 부모 댓글 작성자에게 알림
        parent_comment = await comment_models.get_comment_by_id(comment.parent_id)
        if parent_comment and parent_comment.author_id:
            await notification_models.create_notification(
                user_id=parent_comment.author_id,
                notification_type="comment",
                post_id=post_id,
                actor_id=current_user.id,
                comment_id=comment.id,
            )
    else:
        # 일반 댓글 → 게시글 작성자에게 알림
        if post.author_id:
            await notification_models.create_notification(
                user_id=post.author_id,
                notification_type="comment",
                post_id=post_id,
                actor_id=current_user.id,
                comment_id=comment.id,
            )
except Exception:
    import logging
    logging.getLogger(__name__).warning("알림 생성 실패", exc_info=True)
```

**참고**: `comment_models.get_comment_by_id`가 없으면 추가해야 합니다. 서브에이전트가 확인 후 필요 시 구현하세요.

### Step 2: 알림 트리거 — like_controller.py 수정

`controllers/like_controller.py`의 `like_post` 함수에서, `await like_models.add_like(...)` 성공 후 (try 블록 안, IntegrityError 바깥):

```python
# 알림 생성 (실패해도 좋아요에 영향 없음)
try:
    from models import notification_models

    if post.author_id:
        await notification_models.create_notification(
            user_id=post.author_id,
            notification_type="like",
            post_id=post_id,
            actor_id=current_user.id,
        )
except Exception:
    import logging
    logging.getLogger(__name__).warning("좋아요 알림 생성 실패", exc_info=True)
```

### Step 3: notification_controller.py 생성

`controllers/notification_controller.py` 생성:

```python
"""notification_controller: 알림 관련 컨트롤러."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models import notification_models
from models.user_models import User
from schemas.common import create_response
from utils.exceptions import not_found_error


async def get_notifications(
    current_user: User, request: Request, offset: int = 0, limit: int = 20
) -> dict:
    """내 알림 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    notifications, total_count = await notification_models.get_notifications(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    return create_response(
        "NOTIFICATIONS_LOADED",
        "알림 목록을 조회했습니다.",
        data={
            "notifications": notifications,
            "pagination": {
                "total_count": total_count,
                "has_more": has_more,
            },
        },
        timestamp=timestamp,
    )


async def get_unread_count(current_user: User, request: Request) -> dict:
    """읽지 않은 알림 수를 조회합니다."""
    timestamp = get_request_timestamp(request)
    count = await notification_models.get_unread_count(current_user.id)

    return create_response(
        "UNREAD_COUNT",
        "읽지 않은 알림 수를 조회했습니다.",
        data={"unread_count": count},
        timestamp=timestamp,
    )


async def mark_as_read(
    notification_id: int, current_user: User, request: Request
) -> dict:
    """알림을 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)

    success = await notification_models.mark_as_read(notification_id, current_user.id)
    if not success:
        raise not_found_error("notification", timestamp)

    return create_response(
        "NOTIFICATION_READ",
        "알림을 읽음 처리했습니다.",
        timestamp=timestamp,
    )


async def mark_all_as_read(current_user: User, request: Request) -> dict:
    """모든 알림을 읽음 처리합니다."""
    timestamp = get_request_timestamp(request)

    count = await notification_models.mark_all_as_read(current_user.id)

    return create_response(
        "ALL_NOTIFICATIONS_READ",
        f"{count}개의 알림을 읽음 처리했습니다.",
        timestamp=timestamp,
    )


async def delete_notification(
    notification_id: int, current_user: User, request: Request
) -> dict:
    """알림을 삭제합니다."""
    timestamp = get_request_timestamp(request)

    success = await notification_models.delete_notification(
        notification_id, current_user.id
    )
    if not success:
        raise not_found_error("notification", timestamp)

    return create_response(
        "NOTIFICATION_DELETED",
        "알림을 삭제했습니다.",
        timestamp=timestamp,
    )
```

### Step 4: notification_router.py 생성

`routers/notification_router.py` 생성:

```python
"""notification_router: 알림 API 라우터."""

from fastapi import APIRouter, Depends, Query, Request

from controllers import notification_controller
from dependencies.auth import get_current_user
from models.user_models import User

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("/")
async def get_notifications(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.get_notifications(
        current_user, request, offset, limit
    )


@router.get("/unread-count")
async def get_unread_count(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.get_unread_count(current_user, request)


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.mark_as_read(
        notification_id, current_user, request
    )


@router.patch("/read-all")
async def mark_all_as_read(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.mark_all_as_read(current_user, request)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await notification_controller.delete_notification(
        notification_id, current_user, request
    )
```

**주의**: `/read-all` 경로를 `/{notification_id}/read`보다 먼저 등록하거나, 라우트 순서에 주의하세요 (FastAPI 라우트 순서 규칙).

### Step 5: main.py에 알림 라우터 등록

`main.py`의 라우터 등록 섹션에 추가:

```python
from routers import notification_router
app.include_router(notification_router.router)
```

### Step 6: 테스트 통과 확인

```bash
pytest tests/test_notifications.py -v
pytest -x -v  # 전체 테스트
```

### Step 7: 커밋

```bash
git add controllers/comment_controller.py controllers/like_controller.py \
    controllers/notification_controller.py routers/notification_router.py main.py
git commit -m "feat: notification triggers + API router + tests"
```

---

## Task 6: 내 활동 백엔드

내가 쓴 글, 내가 쓴 댓글, 좋아요한 글 API를 구현합니다.

**Files:**
- Create: `models/activity_models.py`
- Create: `controllers/activity_controller.py`
- Modify: `routers/user_router.py`
- Create: `tests/test_my_activity.py`

### Step 1: 테스트 작성

`tests/test_my_activity.py` 생성:

```python
"""내 활동 API 테스트."""

import pytest


@pytest.mark.asyncio
async def test_my_posts(authorized_user):
    """내가 쓴 글 목록을 조회합니다."""
    client, _, _ = authorized_user

    await client.post("/v1/posts/", json={"title": "내 글 1", "content": "내용"})
    await client.post("/v1/posts/", json={"title": "내 글 2", "content": "내용"})

    res = await client.get("/v1/users/me/posts")
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["posts"]) == 2
    assert data["pagination"]["total_count"] == 2


@pytest.mark.asyncio
async def test_my_comments(authorized_user):
    """내가 쓴 댓글 목록을 조회합니다."""
    client, _, _ = authorized_user

    post_res = await client.post(
        "/v1/posts/", json={"title": "게시글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    await client.post(f"/v1/posts/{post_id}/comments", json={"content": "댓글 1"})
    await client.post(f"/v1/posts/{post_id}/comments", json={"content": "댓글 2"})

    res = await client.get("/v1/users/me/comments")
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["comments"]) == 2
    assert data["comments"][0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_my_likes(authorized_user):
    """좋아요한 글 목록을 조회합니다."""
    client, _, _ = authorized_user

    post_res = await client.post(
        "/v1/posts/", json={"title": "게시글", "content": "내용"}
    )
    post_id = post_res.json()["data"]["post_id"]

    await client.post(f"/v1/posts/{post_id}/likes", json={})

    res = await client.get("/v1/users/me/likes")
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data["posts"]) == 1
    assert data["posts"][0]["post_id"] == post_id


@pytest.mark.asyncio
async def test_my_activity_unauthenticated(client):
    """미로그인 시 401을 반환합니다."""
    res = await client.get("/v1/users/me/posts")
    assert res.status_code == 401
```

### Step 2: activity_models.py 구현

`models/activity_models.py` 생성:

```python
"""activity_models: 내 활동 관련 모델."""

from database.connection import get_connection
from schemas.common import build_author_dict
from utils.formatters import format_datetime


async def get_my_posts(
    user_id: int, offset: int = 0, limit: int = 10
) -> tuple[list[dict], int]:
    """내가 쓴 글 목록을 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM post
                WHERE author_id = %s AND deleted_at IS NULL
                """,
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT p.id, p.title, p.content, p.image_url, p.views,
                       p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comment
                        WHERE post_id = p.id AND deleted_at IS NULL) AS comments_count
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                WHERE p.author_id = %s AND p.deleted_at IS NULL
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    posts = []
    for row in rows:
        posts.append({
            "post_id": row[0],
            "title": row[1],
            "content": (row[2] or "")[:200],
            "image_url": row[3],
            "views_count": row[4],
            "created_at": format_datetime(row[5]),
            "updated_at": format_datetime(row[6]),
            "author": build_author_dict(row[7], row[8], row[9]),
            "likes_count": row[10],
            "comments_count": row[11],
        })

    return posts, total_count


async def get_my_comments(
    user_id: int, offset: int = 0, limit: int = 10
) -> tuple[list[dict], int]:
    """내가 쓴 댓글 목록을 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM comment
                WHERE author_id = %s AND deleted_at IS NULL
                """,
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT c.id, c.content, c.created_at, c.post_id, p.title
                FROM comment c
                LEFT JOIN post p ON c.post_id = p.id
                WHERE c.author_id = %s AND c.deleted_at IS NULL
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    comments = []
    for row in rows:
        comments.append({
            "comment_id": row[0],
            "content": row[1],
            "created_at": format_datetime(row[2]),
            "post_id": row[3],
            "post_title": row[4] or "삭제된 게시글",
        })

    return comments, total_count


async def get_my_likes(
    user_id: int, offset: int = 0, limit: int = 10
) -> tuple[list[dict], int]:
    """좋아요한 글 목록을 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM post_like pl
                JOIN post p ON pl.post_id = p.id
                WHERE pl.user_id = %s AND p.deleted_at IS NULL
                """,
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT p.id, p.title, p.content, p.image_url, p.views,
                       p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comment
                        WHERE post_id = p.id AND deleted_at IS NULL) AS comments_count
                FROM post_like pl
                JOIN post p ON pl.post_id = p.id
                LEFT JOIN user u ON p.author_id = u.id
                WHERE pl.user_id = %s AND p.deleted_at IS NULL
                ORDER BY pl.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    posts = []
    for row in rows:
        posts.append({
            "post_id": row[0],
            "title": row[1],
            "content": (row[2] or "")[:200],
            "image_url": row[3],
            "views_count": row[4],
            "created_at": format_datetime(row[5]),
            "updated_at": format_datetime(row[6]),
            "author": build_author_dict(row[7], row[8], row[9]),
            "likes_count": row[10],
            "comments_count": row[11],
        })

    return posts, total_count
```

### Step 3: activity_controller.py 생성

`controllers/activity_controller.py` 생성:

```python
"""activity_controller: 내 활동 관련 컨트롤러."""

from fastapi import Request

from dependencies.request_context import get_request_timestamp
from models import activity_models
from models.user_models import User
from schemas.common import create_response


async def get_my_posts(
    current_user: User, request: Request, offset: int = 0, limit: int = 10
) -> dict:
    """내가 쓴 글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    posts, total_count = await activity_models.get_my_posts(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    return create_response(
        "MY_POSTS_LOADED",
        "내가 쓴 글 목록을 조회했습니다.",
        data={
            "posts": posts,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_my_comments(
    current_user: User, request: Request, offset: int = 0, limit: int = 10
) -> dict:
    """내가 쓴 댓글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    comments, total_count = await activity_models.get_my_comments(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    return create_response(
        "MY_COMMENTS_LOADED",
        "내가 쓴 댓글 목록을 조회했습니다.",
        data={
            "comments": comments,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )


async def get_my_likes(
    current_user: User, request: Request, offset: int = 0, limit: int = 10
) -> dict:
    """좋아요한 글 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    posts, total_count = await activity_models.get_my_likes(
        current_user.id, offset, limit
    )
    has_more = offset + limit < total_count

    return create_response(
        "MY_LIKES_LOADED",
        "좋아요한 글 목록을 조회했습니다.",
        data={
            "posts": posts,
            "pagination": {"total_count": total_count, "has_more": has_more},
        },
        timestamp=timestamp,
    )
```

### Step 4: user_router.py에 내 활동 라우트 추가

`routers/user_router.py`에서 `GET /me` 라우트 근처에 추가 (**`/{user_id}` 동적 경로보다 위에 배치**):

```python
from controllers import activity_controller

@router.get("/me/posts")
async def get_my_posts(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await activity_controller.get_my_posts(current_user, request, offset, limit)

@router.get("/me/comments")
async def get_my_comments(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await activity_controller.get_my_comments(current_user, request, offset, limit)

@router.get("/me/likes")
async def get_my_likes(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    return await activity_controller.get_my_likes(current_user, request, offset, limit)
```

`Query` import 추가: `from fastapi import ..., Query`

### Step 5: 테스트 통과 확인

```bash
pytest tests/test_my_activity.py -v
pytest -x -v
```

### Step 6: 커밋

```bash
git add models/activity_models.py controllers/activity_controller.py \
    routers/user_router.py tests/test_my_activity.py
git commit -m "feat: my activity backend (posts, comments, likes)"
```

---

## Task 7: 타 사용자 프로필 백엔드

게시글 목록에 `author_id` 필터를 추가하고, 공개 프로필 API를 정리합니다.

**Files:**
- Modify: `models/post_models.py` (`get_posts_with_details`에 `author_id` 파라미터 추가)
- Modify: `services/post_service.py` (author_id 전달)
- Modify: `controllers/post_controller.py` (author_id 쿼리 파라미터)
- Modify: `routers/post_router.py` (author_id 쿼리 파라미터)
- Create: `tests/test_user_profile.py`

### Step 1: 테스트 작성

`tests/test_user_profile.py` 생성:

```python
"""타 사용자 프로필 관련 테스트."""

import pytest


@pytest.mark.asyncio
async def test_get_user_profile(authorized_user, client):
    """타 사용자 프로필을 조회합니다."""
    _, user_info, _ = authorized_user
    user_id = user_info["user_id"]

    res = await client.get(f"/v1/users/{user_id}")
    assert res.status_code == 200

    data = res.json()["data"]
    assert data["user_id"] == user_id
    assert "nickname" in data
    assert "email" not in data  # 비공개


@pytest.mark.asyncio
async def test_filter_posts_by_author(authorized_user):
    """author_id로 게시글을 필터링합니다."""
    client, user_info, _ = authorized_user
    user_id = user_info["user_id"]

    await client.post("/v1/posts/", json={"title": "내 글", "content": "내용"})

    res = await client.get(f"/v1/posts/?author_id={user_id}")
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1
    for post in posts:
        assert post["author"]["user_id"] == user_id
```

### Step 2: post_models.py의 get_posts_with_details에 author_id 파라미터 추가

기존 `get_posts_with_details` 함수 시그니처에 `author_id: int | None = None` 추가.

WHERE 절에 조건 추가:

```python
if author_id is not None:
    where_clauses.append("p.author_id = %s")
    params.append(author_id)
```

### Step 3: services/post_service.py의 get_posts에 author_id 전달

`PostService.get_posts` 시그니처에 `author_id: int | None = None` 추가, `post_models.get_posts_with_details(... author_id=author_id)` 호출.

총 개수 쿼리(`get_total_post_count` 또는 유사 함수)에도 `author_id` 조건 추가.

### Step 4: controllers/post_controller.py의 get_posts에 author_id 전달

`get_posts` 시그니처에 `author_id: int | None = None` 추가, `PostService.get_posts(... author_id=author_id)` 호출.

### Step 5: routers/post_router.py에 author_id 쿼리 파라미터 추가

`GET /v1/posts/`에 `author_id: int | None = Query(None)` 추가.

### Step 6: 타 사용자 프로필 응답에서 이메일 제외

`controllers/user_controller.py`의 `get_user_info` 함수 확인. 타 사용자 조회 시 (`user_id != current_user.id`) 이메일을 제외하는 응답을 반환하도록 확인 또는 수정:

```python
user_data = {
    "user_id": user.id,
    "nickname": user.nickname,
    "profileImageUrl": user.profileImageUrl,
    "created_at": format_datetime(user.created_at),
}
# 본인이면 이메일도 포함
if current_user and current_user.id == user.id:
    user_data["email"] = user.email
```

### Step 7: 테스트 통과 확인

```bash
pytest tests/test_user_profile.py -v
pytest -x -v
```

### Step 8: 커밋

```bash
git add models/post_models.py services/post_service.py controllers/post_controller.py \
    routers/post_router.py controllers/user_controller.py tests/test_user_profile.py
git commit -m "feat: user profile backend (author_id filter, public profile)"
```

---

## Task 8: 프론트엔드 — 공통 업데이트 (constants, config, HTML 템플릿)

프론트엔드 전체에서 공유되는 상수, 설정, CSS를 업데이트합니다.

**Files (모두 `2-cho-community-fe/` 기준):**
- Modify: `js/constants.js`
- Modify: `js/config.js` (HTML_PATHS가 여기에 있으면)

### Step 1: constants.js에 새 엔드포인트/경로/메시지 추가

`js/constants.js` 수정:

`API_ENDPOINTS`에 추가:

```javascript
NOTIFICATIONS: {
    ROOT: '/v1/notifications',
    UNREAD_COUNT: '/v1/notifications/unread-count',
    READ: (id) => `/v1/notifications/${id}/read`,
    READ_ALL: '/v1/notifications/read-all',
    DELETE: (id) => `/v1/notifications/${id}`,
},
VERIFICATION: {
    VERIFY: '/v1/auth/verify-email',
    RESEND: '/v1/auth/resend-verification',
},
ACTIVITY: {
    MY_POSTS: '/v1/users/me/posts',
    MY_COMMENTS: '/v1/users/me/comments',
    MY_LIKES: '/v1/users/me/likes',
},
```

`NAV_PATHS`에 추가:

```javascript
NOTIFICATIONS: '/notifications',
MY_ACTIVITY: '/my-activity',
VERIFY_EMAIL: '/verify-email',
USER_PROFILE: (id) => `/user-profile?id=${id}`,
```

`HTML_PATHS`에 추가:

```javascript
'/notifications': '/notifications.html',
'/my-activity': '/my-activity.html',
'/verify-email': '/verify-email.html',
'/user-profile': '/user-profile.html',
```

`UI_MESSAGES`에 추가:

```javascript
EMAIL_NOT_VERIFIED: '이메일 인증 후 이용 가능합니다.',
VERIFICATION_SENT: '인증 메일을 발송했습니다.',
NOTIFICATION_LOAD_FAIL: '알림 목록을 불러오지 못했습니다.',
```

### Step 2: 새 HTML 페이지 4개 생성

기존 `post_detail.html` 구조를 참고하여 생성:

- `verify-email.html` — 인증 결과 표시 페이지
- `notifications.html` — 알림 목록 페이지
- `my-activity.html` — 내 활동 페이지 (탭 UI)
- `user-profile.html` — 타 사용자 프로필 페이지

각 HTML의 기본 구조:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>페이지 제목 - 아무 말 대잔치</title>
    <link rel="stylesheet" href="css/index.css">
</head>
<body>
    <header id="auth-section" class="header"><!-- HeaderController가 채움 --></header>
    <main class="container">
        <button id="back-btn" class="back-button">
            <svg><!-- chevron SVG --></svg>
        </button>
        <!-- 페이지별 콘텐츠 -->
    </main>
    <script type="module" src="js/app/pageName.js"></script>
</body>
</html>
```

### Step 3: 커밋

```bash
git add js/constants.js *.html
git commit -m "feat: frontend shared constants + HTML templates for Phase 2"
```

---

## Task 9: 프론트엔드 — 이메일 인증 + 알림 시스템 UI

이메일 인증 페이지, 미인증 안내 UI, 헤더 알림 뱃지, 알림 목록 페이지를 구현합니다.

**Files (모두 `2-cho-community-fe/` 기준):**
- Create: `js/app/verifyEmail.js`
- Create: `js/controllers/VerifyEmailController.js`
- Create: `js/models/NotificationModel.js`
- Create: `js/app/notifications.js`
- Create: `js/controllers/NotificationController.js`
- Create: `js/views/NotificationView.js`
- Modify: `js/controllers/HeaderController.js` (알림 뱃지 + 폴링)
- Modify: `js/models/AuthModel.js` (email_verified 전달)
- Create: `css/modules/notifications.css`

### Step 1: VerifyEmailController 구현

`js/controllers/VerifyEmailController.js`:

```javascript
import ApiService from '../services/ApiService.js';
import { API_ENDPOINTS } from '../constants.js';

class VerifyEmailController {
    async init() {
        const params = new URLSearchParams(location.search);
        const token = params.get('token');
        const resultEl = document.getElementById('verify-result');

        if (!token) {
            resultEl.textContent = '유효하지 않은 인증 링크입니다.';
            return;
        }

        const result = await ApiService.post(API_ENDPOINTS.VERIFICATION.VERIFY, { token });

        if (result.ok) {
            resultEl.textContent = '이메일 인증이 완료되었습니다! 로그인 페이지로 이동합니다.';
            setTimeout(() => { location.href = '/login'; }, 2000);
        } else {
            resultEl.textContent = '유효하지 않거나 만료된 인증 링크입니다.';
        }
    }
}

export default VerifyEmailController;
```

### Step 2: NotificationModel 구현

`js/models/NotificationModel.js`:

```javascript
import ApiService from '../services/ApiService.js';
import { API_ENDPOINTS } from '../constants.js';

class NotificationModel {
    static async getNotifications(offset = 0, limit = 20) {
        return ApiService.get(
            `${API_ENDPOINTS.NOTIFICATIONS.ROOT}?offset=${offset}&limit=${limit}`
        );
    }

    static async getUnreadCount() {
        return ApiService.get(API_ENDPOINTS.NOTIFICATIONS.UNREAD_COUNT);
    }

    static async markAsRead(id) {
        return ApiService.patch(API_ENDPOINTS.NOTIFICATIONS.READ(id));
    }

    static async markAllAsRead() {
        return ApiService.patch(API_ENDPOINTS.NOTIFICATIONS.READ_ALL);
    }

    static async deleteNotification(id) {
        return ApiService.delete(API_ENDPOINTS.NOTIFICATIONS.DELETE(id));
    }
}

export default NotificationModel;
```

### Step 3: HeaderController에 알림 폴링 추가

`js/controllers/HeaderController.js` 수정:

- `init()` 메서드에서 로그인 상태일 때 알림 뱃지 렌더링 + 30초 폴링 시작
- `destroy()` 또는 로그아웃 시 `clearInterval`

주요 로직:

```javascript
// init() 내부, 로그인 성공 후
this._startNotificationPolling();

_startNotificationPolling() {
    this._pollNotifications();  // 즉시 1회 호출
    this._notifInterval = setInterval(() => this._pollNotifications(), 30000);
}

async _pollNotifications() {
    const result = await NotificationModel.getUnreadCount();
    if (result.ok) {
        const count = result.data?.data?.unread_count || 0;
        HeaderView.updateNotificationBadge(count);
    }
}
```

`HeaderView`에 알림 아이콘 + 뱃지 렌더링 메서드 추가.

### Step 4: NotificationController + NotificationView 구현

알림 목록 페이지의 MVC. `MainController`의 무한 스크롤 패턴을 참고하여 구현합니다.

각 알림 항목 클릭 시:
1. `NotificationModel.markAsRead(id)` 호출
2. `location.href = resolveNavPath(NAV_PATHS.DETAIL(notification.post_id))` 이동

### Step 5: 미인증 안내 UI 구현

글쓰기/댓글/좋아요 시도 시 `email_verified === false`이면:
- `HeaderController.getCurrentUser().email_verified`로 확인
- 안내 토스트 표시 + 재발송 버튼

이 로직은 각 컨트롤러(MainController, DetailController, CommentController)에서 분기.

### Step 6: 커밋

```bash
git add js/app/verifyEmail.js js/app/notifications.js \
    js/controllers/VerifyEmailController.js js/controllers/NotificationController.js \
    js/models/NotificationModel.js js/views/NotificationView.js \
    js/controllers/HeaderController.js css/modules/notifications.css
git commit -m "feat: frontend email verification + notification UI"
```

---

## Task 10: 프론트엔드 — 내 활동 페이지

탭 UI로 내 글/댓글/좋아요를 전환하는 페이지를 구현합니다.

**Files (모두 `2-cho-community-fe/` 기준):**
- Create: `js/app/myActivity.js`
- Create: `js/controllers/MyActivityController.js`
- Create: `js/models/ActivityModel.js`
- Create: `js/views/ActivityView.js`
- Create: `css/modules/activity.css`

### Step 1: ActivityModel 구현

`js/models/ActivityModel.js`:

```javascript
import ApiService from '../services/ApiService.js';
import { API_ENDPOINTS } from '../constants.js';

class ActivityModel {
    static async getMyPosts(offset = 0, limit = 10) {
        return ApiService.get(
            `${API_ENDPOINTS.ACTIVITY.MY_POSTS}?offset=${offset}&limit=${limit}`
        );
    }

    static async getMyComments(offset = 0, limit = 10) {
        return ApiService.get(
            `${API_ENDPOINTS.ACTIVITY.MY_COMMENTS}?offset=${offset}&limit=${limit}`
        );
    }

    static async getMyLikes(offset = 0, limit = 10) {
        return ApiService.get(
            `${API_ENDPOINTS.ACTIVITY.MY_LIKES}?offset=${offset}&limit=${limit}`
        );
    }
}

export default ActivityModel;
```

### Step 2: MyActivityController 구현

`MainController`의 무한 스크롤 + 검색/정렬 패턴을 재활용합니다.

핵심 구조:

```javascript
class MyActivityController {
    constructor() {
        this.currentTab = 'posts';  // 'posts' | 'comments' | 'likes'
        this.currentOffset = 0;
        this.LIMIT = 10;
        this.isLoading = false;
        this.hasMore = true;
    }

    async init() {
        this._setupTabs();
        this._setupInfiniteScroll();
        await this._loadData();
    }

    _setupTabs() {
        // 탭 버튼 클릭 시 currentTab 변경 + _resetAndReload()
    }

    _resetAndReload() {
        this.currentOffset = 0;
        this.hasMore = true;
        this.isLoading = false;
        // 목록 비우기 + _loadData()
    }

    async _loadData() {
        // currentTab에 따라 ActivityModel의 다른 메서드 호출
        // 응답 데이터를 ActivityView로 렌더링
    }
}
```

### Step 3: ActivityView 구현

- 글 목록: `PostListView.createPostCard()` 재사용 가능
- 댓글 목록: 별도 카드 (댓글 내용 + 게시글 제목 링크)

### Step 4: 헤더/프로필에 "내 활동" 진입점 추가

`HeaderController`의 드롭다운 메뉴에 "내 활동" 항목 추가.

### Step 5: 커밋

```bash
git add js/app/myActivity.js js/controllers/MyActivityController.js \
    js/models/ActivityModel.js js/views/ActivityView.js css/modules/activity.css
git commit -m "feat: frontend my activity page (tabs + infinite scroll)"
```

---

## Task 11: 프론트엔드 — 타 사용자 프로필 + 닉네임 링크

닉네임 클릭 시 사용자 프로필 페이지로 이동하는 기능을 구현합니다.

**Files (모두 `2-cho-community-fe/` 기준):**
- Create: `js/app/userProfile.js`
- Create: `js/controllers/UserProfileController.js`
- Create: `js/views/UserProfileView.js`
- Modify: `js/models/UserModel.js` (getUserById 추가)
- Modify: `js/models/PostModel.js` (author_id 파라미터 추가)
- Modify: `js/views/PostListView.js` (닉네임 클릭 이벤트)
- Modify: `js/views/CommentListView.js` (닉네임 클릭 이벤트)
- Modify: `js/views/PostDetailView.js` (닉네임 클릭 이벤트)
- Create: `css/modules/user-profile.css`

### Step 1: UserModel에 getUserById 추가

```javascript
static async getUserById(userId) {
    return ApiService.get(`${API_ENDPOINTS.USERS.ROOT}/${userId}`);
}
```

### Step 2: PostModel에 author_id 파라미터 추가

`getPosts` 메서드에 `authorId` 파라미터 추가:

```javascript
static async getPosts(offset, limit, search, sort, authorId) {
    let url = `${API_ENDPOINTS.POSTS.ROOT}?offset=${offset}&limit=${limit}&sort=${sort}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (authorId) url += `&author_id=${authorId}`;
    return ApiService.get(url);
}
```

### Step 3: UserProfileController 구현

```javascript
class UserProfileController {
    async init(currentUser) {
        const params = new URLSearchParams(location.search);
        const userId = parseInt(params.get('id'));

        // 자기 프로필이면 edit 페이지로 리다이렉트
        if (currentUser && (currentUser.user_id === userId || currentUser.id === userId)) {
            location.href = resolveNavPath(NAV_PATHS.EDIT_PROFILE);
            return;
        }

        await this._loadProfile(userId);
        await this._loadUserPosts(userId);
    }
}
```

### Step 4: 닉네임 클릭 이벤트 추가

**PostListView** (`createPostCard` 내 `.author-nickname` 요소):

```javascript
nicknameEl.style.cursor = 'pointer';
nicknameEl.style.color = '#7C4DFF';
nicknameEl.addEventListener('click', (e) => {
    e.stopPropagation();  // 카드 전체 클릭 방지
    location.href = resolveNavPath(NAV_PATHS.USER_PROFILE(post.author.user_id));
});
```

**PostDetailView** (`#post-author-nickname`):

```javascript
authorNickname.style.cursor = 'pointer';
authorNickname.style.color = '#7C4DFF';
authorNickname.addEventListener('click', () => {
    location.href = resolveNavPath(NAV_PATHS.USER_PROFILE(post.author.user_id));
});
```

**CommentListView** (`createCommentElement` 내 `.comment-author-name` 요소):

동일한 클릭 이벤트 패턴. 탈퇴한 사용자(`user_id === null`)일 때는 이벤트 바인딩하지 않음.

### Step 5: 커밋

```bash
git add js/app/userProfile.js js/controllers/UserProfileController.js \
    js/views/UserProfileView.js js/models/UserModel.js js/models/PostModel.js \
    js/views/PostListView.js js/views/CommentListView.js js/views/PostDetailView.js \
    css/modules/user-profile.css
git commit -m "feat: frontend user profile page + nickname links"
```

---

## Task 12: CI + Lint + 최종 검증

모든 백엔드 테스트, lint, 타입 체크를 실행하여 Phase 2 전체를 검증합니다.

**Step 1: Ruff 린팅**

```bash
cd 2-cho-community-be
ruff check .
ruff check . --fix  # 자동 수정
```

**Step 2: Mypy 타입 체크**

```bash
mypy .
```

**Step 3: 전체 테스트**

```bash
pytest -v
```

**Step 4: 린트 에러 수정 후 최종 커밋**

```bash
git add -A
git commit -m "fix: Phase 2 lint and type check fixes"
```

---

## 작업 순서 요약

| Task | 내용 | 의존성 |
| ---- | ---- | ------ |
| 1 | DB 스키마 + User 모델 + 테스트 인프라 | 없음 |
| 2 | 이메일 인증 백엔드 | Task 1 |
| 3 | 이메일 인증 가드 | Task 2 |
| 4 | 알림 모델 + 테스트 | Task 1 |
| 5 | 알림 트리거 + API | Task 4 |
| 6 | 내 활동 백엔드 | Task 1 |
| 7 | 타 사용자 프로필 백엔드 | Task 1 |
| 8 | 프론트엔드 공통 업데이트 | Task 1-7 |
| 9 | 프론트엔드 이메일 인증 + 알림 | Task 8 |
| 10 | 프론트엔드 내 활동 | Task 8 |
| 11 | 프론트엔드 타 사용자 프로필 | Task 8 |
| 12 | CI + Lint + 최종 검증 | Task 1-11 |

**참고**: Task 4, 6, 7은 서로 독립적이므로 병렬 실행 가능합니다.
