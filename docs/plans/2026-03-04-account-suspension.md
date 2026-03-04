# Account Suspension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 관리자가 악의적 사용자를 기간 정지할 수 있는 시스템. 로그인/API 접근 차단, 신고 처리 시 연동.

**Architecture:** `user` 테이블에 `suspended_until`, `suspended_reason` 컬럼 추가. `_validate_token()`과 로그인에서 정지 상태 체크. 관리자 전용 API로 정지/해제 관리. 신고 resolved 시 선택적 정지 연동.

**Tech Stack:** FastAPI, aiomysql, Pydantic v2, pytest (async)

---

### Task 1: DB 스키마 변경

**Files:**
- Modify: `database/schema.sql:2-13`
- Create: `database/migration_suspension.sql`

**Step 1: `schema.sql`에 컬럼 추가**

`user` 테이블 정의에 `suspended_until`, `suspended_reason` 컬럼을 `role` 뒤에 추가:

```sql
-- user 테이블 (schema.sql 수정)
CREATE TABLE user (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    email_verified TINYINT(1) NOT NULL DEFAULT 0,
    nickname varchar(255) NOT NULL UNIQUE,
    password varchar(2048) NOT NULL,
    profile_img varchar(2048) NULL,
    role ENUM('user','admin') NOT NULL DEFAULT 'user',
    suspended_until TIMESTAMP NULL,
    suspended_reason VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);
```

인덱스 섹션 하단에 추가:

```sql
-- 20. 정지 사용자 조회
CREATE INDEX idx_user_suspended ON user (suspended_until);
```

**Step 2: 마이그레이션 스크립트 생성**

```sql
-- database/migration_suspension.sql
-- 계정 정지 기능 마이그레이션

ALTER TABLE user
    ADD COLUMN suspended_until TIMESTAMP NULL AFTER role,
    ADD COLUMN suspended_reason VARCHAR(500) NULL AFTER suspended_until;

CREATE INDEX idx_user_suspended ON user (suspended_until);
```

**Step 3: Commit**

```bash
cd 2-cho-community-be
git add database/schema.sql database/migration_suspension.sql
git commit -m "feat: add suspended_until, suspended_reason columns to user table"
```

---

### Task 2: User dataclass 확장

**Files:**
- Modify: `models/user_models.py:18-60` (User dataclass)
- Modify: `models/user_models.py:63-65` (USER_SELECT_FIELDS)
- Modify: `models/user_models.py:68-88` (_row_to_user)

**Step 1: User dataclass에 필드 추가**

`models/user_models.py`의 `User` dataclass에 `suspended_until`, `suspended_reason` 필드와 `is_suspended` 프로퍼티 추가:

```python
from datetime import datetime, timezone

@dataclass(frozen=True)
class User:
    id: int
    email: str
    password: str
    nickname: str
    email_verified: bool = False
    profile_image_url: str | None = None
    role: str = "user"
    suspended_until: datetime | None = None
    suspended_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_suspended(self) -> bool:
        """사용자가 현재 정지 상태인지 확인합니다."""
        if self.suspended_until is None:
            return False
        return self.suspended_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)

    @property
    def profileImageUrl(self) -> str:
        return self.profile_image_url or "/assets/profiles/default_profile.jpg"
```

**주의**: MySQL TIMESTAMP는 timezone-naive로 반환될 수 있으므로 `replace(tzinfo=timezone.utc)` 사용.

**Step 2: USER_SELECT_FIELDS 수정**

```python
USER_SELECT_FIELDS = (
    "id, email, email_verified, nickname, password, profile_img, role, "
    "suspended_until, suspended_reason, created_at, updated_at, deleted_at"
)
```

**Step 3: _row_to_user 수정**

인덱스가 2개 밀리므로 기존 `row[7]`(created_at) → `row[9]`, `row[8]`(updated_at) → `row[10]`, `row[9]`(deleted_at) → `row[11]`:

```python
def _row_to_user(row: tuple) -> User:
    return User(
        id=row[0],
        email=row[1],
        email_verified=bool(row[2]),
        nickname=row[3],
        password=row[4],
        profile_image_url=row[5],
        role=row[6],
        suspended_until=row[7],
        suspended_reason=row[8],
        created_at=row[9],
        updated_at=row[10],
        deleted_at=row[11],
    )
```

**Step 4: Commit**

```bash
cd 2-cho-community-be
git add models/user_models.py
git commit -m "feat: extend User dataclass with suspension fields"
```

---

### Task 3: 정지/해제 DB 함수 (suspension_models.py)

**Files:**
- Create: `models/suspension_models.py`

**Step 1: 정지/해제 모델 함수 작성**

```python
"""suspension_models: 계정 정지 관련 데이터 모델."""

from datetime import datetime, timedelta, timezone

from database.connection import transactional


async def suspend_user(
    user_id: int,
    duration_days: int,
    reason: str,
) -> bool:
    """사용자를 기간 정지합니다.

    Args:
        user_id: 정지할 사용자 ID.
        duration_days: 정지 기간 (일).
        reason: 정지 사유.

    Returns:
        정지 성공 여부.
    """
    suspended_until = datetime.now(timezone.utc) + timedelta(days=duration_days)

    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE user
            SET suspended_until = %s, suspended_reason = %s
            WHERE id = %s AND deleted_at IS NULL
            """,
            (suspended_until, reason, user_id),
        )
        return cur.rowcount > 0


async def unsuspend_user(user_id: int) -> bool:
    """사용자 정지를 해제합니다.

    Args:
        user_id: 정지 해제할 사용자 ID.

    Returns:
        해제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE user
            SET suspended_until = NULL, suspended_reason = NULL
            WHERE id = %s AND deleted_at IS NULL
            """,
            (user_id,),
        )
        return cur.rowcount > 0
```

**Step 2: Commit**

```bash
cd 2-cho-community-be
git add models/suspension_models.py
git commit -m "feat: add suspension_models with suspend/unsuspend functions"
```

---

### Task 4: 인증 체인에 정지 체크 추가

**Files:**
- Modify: `dependencies/auth.py:25-58` (_validate_token)
- Modify: `controllers/auth_controller.py:59-112` (login)
- Modify: `controllers/auth_controller.py:141-202` (refresh_token)

**Step 1: `_validate_token()`에 정지 체크 추가**

`dependencies/auth.py`의 `_validate_token()`에서 user 조회 후 정지 체크:

```python
async def _validate_token(request: Request) -> User | None:
    raw_token = _extract_bearer_token(request)
    if not raw_token:
        return None

    payload = decode_access_token(raw_token)
    user_id = int(payload["sub"])
    user = await user_models.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )

    # 정지된 사용자는 API 접근 차단
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_suspended",
                "message": "계정이 정지되었습니다.",
                "suspended_until": user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ") if user.suspended_until else None,
                "suspended_reason": user.suspended_reason,
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )

    return user
```

**Step 2: 로그인에 정지 체크 추가**

`controllers/auth_controller.py`의 `login()` 함수에서 비밀번호 검증 성공 후 정지 체크:

```python
async def login(
    credentials: LoginRequest, request: Request, response: Response
) -> dict:
    timestamp = get_request_timestamp(request)

    user = await user_models.get_user_by_email(credentials.email)

    password_valid = await asyncio.to_thread(
        verify_password,
        credentials.password,
        user.password if user else _TIMING_ATTACK_DUMMY_HASH,
    )

    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": timestamp,
            },
        )

    # 정지된 사용자 로그인 차단
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_suspended",
                "message": "계정이 정지되었습니다.",
                "suspended_until": user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ") if user.suspended_until else None,
                "suspended_reason": user.suspended_reason,
                "timestamp": timestamp,
            },
        )

    # ... 이하 기존 코드 (토큰 발급 등)
```

**Step 3: token refresh에 정지 체크 추가**

`controllers/auth_controller.py`의 `refresh_token()` 함수에서 user 조회 후 정지 체크:

```python
    user = await user_models.get_user_by_id(token_record["user_id"])
    if not user:
        _clear_refresh_cookie(response)
        raise HTTPException(...)

    # 정지된 사용자 토큰 갱신 차단
    if user.is_suspended:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_suspended",
                "message": "계정이 정지되었습니다.",
                "suspended_until": user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ") if user.suspended_until else None,
                "suspended_reason": user.suspended_reason,
                "timestamp": timestamp,
            },
        )
```

**Step 4: Commit**

```bash
cd 2-cho-community-be
git add dependencies/auth.py controllers/auth_controller.py
git commit -m "feat: block suspended users from login and API access"
```

---

### Task 5: 관리자 정지/해제 API

**Files:**
- Create: `schemas/suspension_schemas.py`
- Create: `controllers/suspension_controller.py`
- Modify: `routers/report_router.py` (관리자 정지 라우트 추가)
- Modify: `main.py` (라우터 등록 — report_router에 추가하므로 불필요)

**Step 1: Pydantic 스키마 작성**

```python
# schemas/suspension_schemas.py
"""suspension_schemas: 계정 정지 관련 Pydantic 모델."""

from pydantic import BaseModel, Field, field_validator


class SuspendUserRequest(BaseModel):
    """사용자 정지 요청 모델."""

    duration_days: int = Field(..., ge=1, le=365, description="정지 기간 (일, 1~365)")
    reason: str = Field(..., min_length=1, max_length=500, description="정지 사유")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("정지 사유를 입력해주세요.")
        return v
```

**Step 2: 컨트롤러 작성**

```python
# controllers/suspension_controller.py
"""suspension_controller: 계정 정지 관련 컨트롤러."""

from fastapi import HTTPException, Request, status

from dependencies.request_context import get_request_timestamp
from models import user_models, suspension_models
from models.user_models import User
from schemas.common import create_response
from schemas.suspension_schemas import SuspendUserRequest
from utils.formatters import format_datetime


async def suspend_user(
    user_id: int,
    suspend_data: SuspendUserRequest,
    current_user: User,
    request: Request,
) -> dict:
    """사용자를 정지합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    # 자기 자신 정지 방지
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "cannot_suspend_self",
                "message": "자기 자신을 정지할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    target_user = await user_models.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 다른 관리자 정지 방지
    if target_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "cannot_suspend_admin",
                "message": "관리자를 정지할 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    success = await suspension_models.suspend_user(
        user_id=user_id,
        duration_days=suspend_data.duration_days,
        reason=suspend_data.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    # 정지 후 사용자 정보 재조회
    updated_user = await user_models.get_user_by_id(user_id)

    return create_response(
        "USER_SUSPENDED",
        "사용자가 정지되었습니다.",
        data={
            "user_id": user_id,
            "suspended_until": format_datetime(updated_user.suspended_until) if updated_user else None,
            "suspended_reason": suspend_data.reason,
            "duration_days": suspend_data.duration_days,
        },
        timestamp=timestamp,
    )


async def unsuspend_user(
    user_id: int,
    current_user: User,
    request: Request,
) -> dict:
    """사용자 정지를 해제합니다 (관리자 전용)."""
    timestamp = get_request_timestamp(request)

    target_user = await user_models.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    success = await suspension_models.unsuspend_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "사용자를 찾을 수 없습니다.",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "USER_UNSUSPENDED",
        "사용자 정지가 해제되었습니다.",
        data={"user_id": user_id},
        timestamp=timestamp,
    )
```

**Step 3: 라우터에 정지/해제 엔드포인트 추가**

`routers/report_router.py` 하단에 관리자 사용자 관리 섹션 추가:

```python
# report_router.py 하단에 추가
from controllers import suspension_controller
from schemas.suspension_schemas import SuspendUserRequest

# ============ 관리자 사용자 관리 ============

@report_router.post(
    "/v1/admin/users/{user_id}/suspend",
    status_code=status.HTTP_200_OK,
)
async def suspend_user(
    user_id: int,
    suspend_data: SuspendUserRequest,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """사용자를 정지합니다 (관리자 전용)."""
    return await suspension_controller.suspend_user(
        user_id, suspend_data, current_user, request
    )


@report_router.delete(
    "/v1/admin/users/{user_id}/suspend",
    status_code=status.HTTP_200_OK,
)
async def unsuspend_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
) -> dict:
    """사용자 정지를 해제합니다 (관리자 전용)."""
    return await suspension_controller.unsuspend_user(
        user_id, current_user, request
    )
```

**Step 4: Rate Limit 추가**

`middleware/rate_limiter.py`의 `RATE_LIMIT_CONFIG`에 추가:

```python
# 관리자 사용자 정지 관리
"/v1/admin/users": {"max_requests": 30, "window_seconds": 60},
```

**Step 5: Commit**

```bash
cd 2-cho-community-be
git add schemas/suspension_schemas.py controllers/suspension_controller.py routers/report_router.py middleware/rate_limiter.py
git commit -m "feat: add admin suspend/unsuspend API endpoints"
```

---

### Task 6: 신고 처리 → 정지 연동

**Files:**
- Modify: `schemas/report_schemas.py:42-53` (ResolveReportRequest)
- Modify: `services/report_service.py:82-123` (resolve_report)

**Step 1: ResolveReportRequest에 suspend_days 추가**

```python
class ResolveReportRequest(BaseModel):
    """신고 처리 요청 모델."""

    status: str = Field(..., description="처리 상태 (resolved, dismissed)")
    suspend_days: int | None = Field(
        None, ge=1, le=365,
        description="사용자 정지 기간 (일, resolved 시에만 적용)"
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_RESOLVE_STATUSES:
            raise ValueError(f"유효하지 않은 처리 상태입니다: {v}")
        return v
```

**Step 2: ReportService.resolve_report()에 정지 로직 추가**

`services/report_service.py`에 `suspension_models` import 추가 후 resolve_report 수정:

```python
from models import report_models, post_models, comment_models, suspension_models

    @staticmethod
    async def resolve_report(
        report_id: int,
        admin_id: int,
        new_status: str,
        timestamp: str,
        suspend_days: int | None = None,
    ) -> Dict:
        """신고를 처리합니다.

        resolved: 대상 콘텐츠를 soft delete합니다.
        dismissed: 대상을 유지합니다.
        suspend_days가 지정되면 콘텐츠 작성자를 정지합니다.
        """
        report = await report_models.get_report_by_id(report_id)
        if not report:
            raise not_found_error("report", timestamp)

        if report.status != "pending":
            raise bad_request_error(
                "already_processed",
                timestamp,
                "이미 처리된 신고입니다.",
            )

        resolved = await report_models.resolve_report(report_id, admin_id, new_status)
        if not resolved:
            raise not_found_error("report", timestamp)

        if new_status == "resolved":
            # 콘텐츠 soft delete
            author_id = None
            if report.target_type == "post":
                post_target = await post_models.get_post_by_id(report.target_id)
                if post_target:
                    author_id = post_target.author_id
                await post_models.delete_post(report.target_id)
            elif report.target_type == "comment":
                comment_target = await comment_models.get_comment_by_id(report.target_id)
                if comment_target:
                    author_id = comment_target.author_id
                await comment_models.delete_comment(report.target_id)

            # 작성자 정지 (관리자 지정 시)
            if suspend_days and author_id:
                reason = f"신고 처리에 의한 정지 (신고 #{report_id}: {report.reason})"
                await suspension_models.suspend_user(
                    user_id=author_id,
                    duration_days=suspend_days,
                    reason=reason,
                )

        return {
            "report_id": resolved.id,
            "status": resolved.status,
            "resolved_by": resolved.resolved_by,
        }
```

**Step 3: report_controller.resolve_report()에 suspend_days 전달**

`controllers/report_controller.py`의 `resolve_report()`에서 `suspend_days` 전달:

```python
    result = await ReportService.resolve_report(
        report_id=report_id,
        admin_id=current_user.id,
        new_status=report_data.status,
        timestamp=timestamp,
        suspend_days=report_data.suspend_days,
    )
```

**Step 4: Commit**

```bash
cd 2-cho-community-be
git add schemas/report_schemas.py services/report_service.py controllers/report_controller.py
git commit -m "feat: integrate user suspension with report resolution"
```

---

### Task 7: serialize_user에 정지 정보 추가

**Files:**
- Modify: `schemas/common.py:59-75` (serialize_user)

**Step 1: serialize_user 수정**

관리자 또는 본인에게 정지 상태를 노출하기 위해 `serialize_user`에 정지 필드 추가:

```python
def serialize_user(user) -> dict[str, Any]:
    result = {
        "user_id": user.id,
        "email": user.email,
        "email_verified": user.email_verified,
        "nickname": user.nickname,
        "profileImageUrl": user.profileImageUrl,
        "role": user.role,
    }
    if user.suspended_until and user.is_suspended:
        result["suspended_until"] = user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ")
        result["suspended_reason"] = user.suspended_reason
    return result
```

**Step 2: Commit**

```bash
cd 2-cho-community-be
git add schemas/common.py
git commit -m "feat: include suspension info in serialized user response"
```

---

### Task 8: 테스트 작성

**Files:**
- Create: `tests/test_suspension.py`

**Step 1: 테스트 파일 작성**

```python
"""test_suspension: 계정 정지 시스템 테스트.

테스트 범위:
- 관리자 정지/해제 API
- 정지된 사용자 로그인 차단
- 정지된 사용자 API 접근 차단
- 정지 기간 만료 시 자동 해제
- 자기 자신/다른 관리자 정지 방지
- 신고 처리 시 정지 연동
"""

import pytest
from httpx import AsyncClient

from database.connection import get_connection


# ==========================================
# 헬퍼 함수
# ==========================================


async def _create_verified_user(client: AsyncClient, fake) -> tuple[str, dict, dict]:
    """인증된 사용자를 생성하고 (access_token, user_info, payload)를 반환합니다."""
    payload = {
        "email": fake.email(),
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
    }
    res = await client.post("/v1/users/", data=payload)
    assert res.status_code == 201

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    data = login_res.json()["data"]
    return data["access_token"], data["user"], payload


async def _make_admin(user_id: int) -> None:
    """사용자를 관리자로 설정합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET role = 'admin' WHERE id = %s", (user_id,),
            )


async def _suspend_user_directly(user_id: int, days: int = 7) -> None:
    """DB에서 직접 사용자를 정지합니다 (테스트 헬퍼)."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = DATE_ADD(NOW(), INTERVAL %s DAY), "
                "suspended_reason = '테스트 정지' WHERE id = %s",
                (days, user_id),
            )


async def _expire_suspension(user_id: int) -> None:
    """정지 기간을 과거로 설정하여 만료시킵니다 (테스트 헬퍼)."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = DATE_SUB(NOW(), INTERVAL 1 DAY) WHERE id = %s",
                (user_id,),
            )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ==========================================
# 1. 관리자 정지 API
# ==========================================


@pytest.mark.asyncio
async def test_admin_suspend_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-01: 관리자가 사용자를 정지할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    user_token, user_info, _ = await _create_verified_user(client, fake)

    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "스팸 게시글 반복 작성"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "USER_SUSPENDED"
    assert data["data"]["duration_days"] == 7


@pytest.mark.asyncio
async def test_admin_unsuspend_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-02: 관리자가 사용자 정지를 해제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    res = await admin_cli.delete(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
    )
    assert res.status_code == 200
    assert res.json()["code"] == "USER_UNSUSPENDED"


@pytest.mark.asyncio
async def test_cannot_suspend_self(client: AsyncClient, authorized_user, fake):
    """SUSPEND-03: 관리자가 자기 자신을 정지할 수 없다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    res = await admin_cli.post(
        f"/v1/admin/users/{admin_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_suspend_self"


@pytest.mark.asyncio
async def test_cannot_suspend_admin(client: AsyncClient, authorized_user, fake):
    """SUSPEND-04: 관리자가 다른 관리자를 정지할 수 없다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, other_admin_info, _ = await _create_verified_user(client, fake)
    await _make_admin(other_admin_info["user_id"])

    res = await admin_cli.post(
        f"/v1/admin/users/{other_admin_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_suspend_admin"


@pytest.mark.asyncio
async def test_non_admin_cannot_suspend(client: AsyncClient, authorized_user, fake):
    """SUSPEND-05: 일반 사용자는 정지 API에 접근할 수 없다."""
    user_cli, _, _ = authorized_user

    _, target_info, _ = await _create_verified_user(client, fake)

    res = await user_cli.post(
        f"/v1/admin/users/{target_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_suspend_nonexistent_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-06: 존재하지 않는 사용자를 정지할 수 없다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    res = await admin_cli.post(
        "/v1/admin/users/99999/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 404


# ==========================================
# 2. 정지된 사용자 로그인/API 차단
# ==========================================


@pytest.mark.asyncio
async def test_suspended_user_cannot_login(client: AsyncClient, fake):
    """SUSPEND-07: 정지된 사용자는 로그인할 수 없다."""
    _, user_info, payload = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "account_suspended"
    assert "suspended_until" in detail
    assert "suspended_reason" in detail


@pytest.mark.asyncio
async def test_suspended_user_cannot_access_api(client: AsyncClient, fake):
    """SUSPEND-08: 정지된 사용자는 기존 토큰으로 API에 접근할 수 없다."""
    token, user_info, _ = await _create_verified_user(client, fake)

    # 토큰 발급 후 정지
    await _suspend_user_directly(user_info["user_id"])

    res = await client.get("/v1/auth/me", headers=_auth(token))
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "account_suspended"


@pytest.mark.asyncio
async def test_suspended_user_cannot_create_post(client: AsyncClient, fake):
    """SUSPEND-09: 정지된 사용자는 게시글을 작성할 수 없다."""
    token, user_info, _ = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    res = await client.post(
        "/v1/posts/",
        json={"title": "Test", "content": "Content", "category_id": 1},
        headers=_auth(token),
    )
    assert res.status_code == 403


# ==========================================
# 3. 정지 기간 만료
# ==========================================


@pytest.mark.asyncio
async def test_expired_suspension_allows_login(client: AsyncClient, fake):
    """SUSPEND-10: 정지 기간이 만료되면 로그인할 수 있다."""
    _, user_info, payload = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    # 정지 만료 처리
    await _expire_suspension(user_info["user_id"])

    res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_expired_suspension_allows_api_access(client: AsyncClient, fake):
    """SUSPEND-11: 정지 기간이 만료되면 API에 접근할 수 있다."""
    token, user_info, _ = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])
    await _expire_suspension(user_info["user_id"])

    res = await client.get("/v1/auth/me", headers=_auth(token))
    assert res.status_code == 200


# ==========================================
# 4. 신고 → 정지 연동
# ==========================================


@pytest.mark.asyncio
async def test_report_resolve_with_suspension(client: AsyncClient, authorized_user, fake):
    """SUSPEND-12: 신고 resolved 시 작성자를 정지할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    # 일반 사용자 게시글 작성
    user_token, user_info, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Bad Post", "content": "Spam content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 관리자가 직접 신고 (다른 사용자로 신고해야 하므로 별도 사용자 생성)
    reporter_token, _, _ = await _create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "spam"},
        headers=_auth(reporter_token),
    )
    assert report_res.status_code == 201
    report_id = report_res.json()["data"]["report_id"]

    # 신고 처리 + 정지
    resolve_res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved", "suspend_days": 30},
    )
    assert resolve_res.status_code == 200

    # 정지된 사용자 로그인 시도
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": (await _get_user_email(user_info["user_id"])), "password": "Password123!"},
    )
    # 정지 또는 사용자 없음 (게시글 삭제로 author_id NULL 가능성)
    # 이 테스트에서는 정지 확인이 핵심이므로 DB 직접 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT suspended_until, suspended_reason FROM user WHERE id = %s",
                (user_info["user_id"],),
            )
            row = await cur.fetchone()
            assert row[0] is not None  # suspended_until이 설정됨
            assert "신고 처리" in row[1]  # 사유에 신고 처리 문구 포함


async def _get_user_email(user_id: int) -> str:
    """사용자 이메일을 조회합니다 (테스트 헬퍼)."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT email FROM user WHERE id = %s", (user_id,))
            row = await cur.fetchone()
            return row[0]


@pytest.mark.asyncio
async def test_report_resolve_without_suspension(client: AsyncClient, authorized_user, fake):
    """SUSPEND-13: 신고 resolved 시 정지 없이 콘텐츠만 삭제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    user_token, user_info, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Bad Post", "content": "Content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    reporter_token, _, _ = await _create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "spam"},
        headers=_auth(reporter_token),
    )
    report_id = report_res.json()["data"]["report_id"]

    # suspend_days 없이 처리
    resolve_res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved"},
    )
    assert resolve_res.status_code == 200

    # 사용자 정지되지 않음
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT suspended_until FROM user WHERE id = %s",
                (user_info["user_id"],),
            )
            row = await cur.fetchone()
            assert row[0] is None


# ==========================================
# 5. 입력 검증
# ==========================================


@pytest.mark.asyncio
async def test_suspend_invalid_duration(client: AsyncClient, authorized_user, fake):
    """SUSPEND-14: duration_days가 범위를 벗어나면 422를 반환한다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)

    # 0일
    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 0, "reason": "테스트"},
    )
    assert res.status_code == 422

    # 366일
    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 366, "reason": "테스트"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_suspend_empty_reason(client: AsyncClient, authorized_user, fake):
    """SUSPEND-15: reason이 비어있으면 422를 반환한다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)

    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "   "},
    )
    assert res.status_code == 422
```

**Step 2: 테스트 실행**

Run: `cd 2-cho-community-be && python -m pytest tests/test_suspension.py -v`
Expected: 15 tests PASS

**Step 3: 전체 테스트 실행**

Run: `cd 2-cho-community-be && python -m pytest -v`
Expected: 기존 155 + 15 = 170 tests PASS

**Step 4: Commit**

```bash
cd 2-cho-community-be
git add tests/test_suspension.py
git commit -m "test: add comprehensive suspension system tests (15 cases)"
```

---

### Task 9: conftest.py 동기화

**Files:**
- Modify: `tests/conftest.py` — 변경 불필요 (user 테이블 TRUNCATE로 suspended 컬럼도 초기화됨)

확인만 하면 됨. `clear_all_data()`의 `TRUNCATE TABLE user`가 이미 모든 컬럼을 초기화하므로 별도 수정 불필요.

---

### Task 10: CLAUDE.md 업데이트

**Files:**
- Modify: `/Users/revenantonthemission/my-community/CLAUDE.md`

**Step 1: Key Patterns 섹션에 계정 정지 패턴 추가**

```markdown
- **계정 정지**: `user.suspended_until` + `suspended_reason` 컬럼. `is_suspended` 프로퍼티로 상태 확인. `_validate_token()`과 `login()`에서 이중 차단. 기간 정지만 지원 (suspended_until > NOW()면 정지 중, NULL이면 정상). 자동 해제 (별도 배치 불필요)
- **정지 API**: `POST /v1/admin/users/{id}/suspend` (정지), `DELETE /v1/admin/users/{id}/suspend` (해제). 자기 자신/다른 관리자 정지 방지. 신고 resolved 시 `suspend_days` 파라미터로 콘텐츠 삭제 + 작성자 정지 동시 처리
```

**Step 2: API Endpoints에 추가**

```markdown
- `/v1/admin/users/{id}/suspend` - 사용자 정지(`POST`, duration_days+reason), 정지 해제(`DELETE`) — 관리자 전용
```

**Step 3: Commit**

```bash
cd 2-cho-community-be
git add ../../CLAUDE.md
git commit -m "docs: update CLAUDE.md with account suspension patterns"
```
