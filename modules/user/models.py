"""user_models: 사용자 관련 데이터 모델 및 함수 모듈.

사용자 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from core.database.connection import get_cursor, transactional
from core.utils.pagination import escape_like


def generate_temp_nickname() -> str:
    """임시 닉네임을 생성합니다 (tmp_ + 6자리)."""
    return f"tmp_{uuid.uuid4().hex[:6]}"


# SQL Injection 방지: 허용된 컬럼명 whitelist
ALLOWED_USER_COLUMNS = {"nickname", "profile_img", "distro"}


@dataclass(frozen=True)
class User:
    """사용자 데이터 클래스."""

    id: int
    email: str
    password: str | None
    nickname: str
    email_verified: bool = False
    nickname_set: bool = True
    profile_image_url: str | None = None
    role: str = "user"
    suspended_until: datetime | None = None
    suspended_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    distro: str | None = None

    @property
    def is_active(self) -> bool:
        """사용자가 활성화 상태인지 확인합니다."""
        return self.deleted_at is None

    @property
    def is_admin(self) -> bool:
        """사용자가 관리자인지 확인합니다."""
        return self.role == "admin"

    @property
    def is_suspended(self) -> bool:
        """사용자가 현재 정지 상태인지 확인합니다."""
        if self.suspended_until is None:
            return False
        suspended = self.suspended_until
        if suspended.tzinfo is None:
            suspended = suspended.replace(tzinfo=UTC)
        return suspended > datetime.now(UTC)

    @property
    def profileImageUrl(self) -> str:
        """프로필 이미지 URL을 반환합니다 (하위 호환성)."""
        return self.profile_image_url or "/assets/profiles/default_profile.jpg"


# DB 컬럼 → dataclass 필드 매핑을 위한 SELECT (profile_img AS profile_image_url)
USER_SELECT_FIELDS = (
    "id, email, email_verified, nickname, nickname_set, password, "
    "profile_img AS profile_image_url, role, "
    "suspended_until, suspended_reason, created_at, updated_at, deleted_at, distro"
)


def _row_to_user(row: dict) -> User:
    """DictCursor 결과를 User 객체로 변환합니다. bool 변환을 보장합니다."""
    return User(
        id=row["id"],
        email=row["email"],
        email_verified=bool(row["email_verified"]),
        nickname=row["nickname"],
        nickname_set=bool(row["nickname_set"]),
        password=row["password"],
        profile_image_url=row["profile_image_url"],
        role=row["role"],
        suspended_until=row["suspended_until"],
        suspended_reason=row["suspended_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        distro=row["distro"],
    )


async def get_user_by_id(user_id: int) -> User | None:
    """ID로 사용자를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def get_user_by_email(email: str) -> User | None:
    """이메일로 사용자를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE email = %s AND deleted_at IS NULL",
            (email,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def get_deleted_user_by_email(email: str) -> User | None:
    """이메일로 탈퇴한 사용자를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE email = %s AND deleted_at IS NOT NULL",
            (email,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def get_user_by_nickname(nickname: str) -> User | None:
    """닉네임으로 사용자를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE nickname = %s AND deleted_at IS NULL",
            (nickname,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def get_users_by_nicknames(nicknames: list[str]) -> dict[str, "User"]:
    """닉네임 목록으로 사용자를 일괄 조회합니다. N+1 멘션 조회를 단일 IN 쿼리로 대체합니다."""
    if not nicknames:
        return {}

    placeholders = ", ".join(["%s"] * len(nicknames))
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE nickname IN ({placeholders}) AND deleted_at IS NULL",
            nicknames,
        )
        rows = await cur.fetchall()

    return {row["nickname"]: _row_to_user(row) for row in rows}


async def search_users_by_nickname(query: str, exclude_user_ids: set[int], limit: int = 10) -> list[dict]:
    """닉네임 접두어로 사용자 검색. 제외 ID set으로 자기 자신/차단 사용자 필터링."""
    if not query or not query.strip():
        return []

    query = query.strip()
    async with get_cursor() as cur:
        if exclude_user_ids:
            placeholders = ",".join(["%s"] * len(exclude_user_ids))
            sql = (
                f"SELECT id, nickname, profile_img FROM user "
                f"WHERE nickname LIKE %s AND deleted_at IS NULL "
                f"AND id NOT IN ({placeholders}) "
                f"ORDER BY nickname LIMIT %s"
            )
            params = [f"{escape_like(query)}%", *exclude_user_ids, limit]
        else:
            sql = (
                "SELECT id, nickname, profile_img FROM user "
                "WHERE nickname LIKE %s AND deleted_at IS NULL "
                "ORDER BY nickname LIMIT %s"
            )
            params = [f"{escape_like(query)}%", limit]

        await cur.execute(sql, params)
        rows = await cur.fetchall()

    from schemas.common import DEFAULT_PROFILE_IMAGE

    return [
        {
            "user_id": row["id"],
            "nickname": row["nickname"],
            "profileImageUrl": row["profile_img"] or DEFAULT_PROFILE_IMAGE,
        }
        for row in rows
    ]


async def get_user_stats(user_id: int) -> dict:
    """사용자 활동 통계 조회 (게시글 수, 댓글 수, 받은 좋아요 수)."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM post WHERE author_id = %s AND deleted_at IS NULL) AS posts_count,
                (SELECT COUNT(*) FROM comment WHERE author_id = %s AND deleted_at IS NULL) AS comments_count,
                (SELECT COUNT(*)
                 FROM post_like pl
                 JOIN post p ON pl.post_id = p.id
                 WHERE p.author_id = %s AND p.deleted_at IS NULL) AS likes_received_count
            """,
            (user_id, user_id, user_id),
        )
        row = await cur.fetchone()

    if row:
        return dict(row)
    return {"posts_count": 0, "comments_count": 0, "likes_received_count": 0}


async def get_user_email_by_nickname(nickname: str) -> str | None:
    """닉네임으로 사용자 이메일을 조회합니다 (이메일 찾기용)."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT email FROM user WHERE nickname = %s AND deleted_at IS NULL",
            (nickname,),
        )
        row = await cur.fetchone()
        return row["email"] if row else None


async def get_deleted_user_by_nickname(nickname: str) -> User | None:
    """닉네임으로 탈퇴한 사용자를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE nickname = %s AND deleted_at IS NOT NULL",
            (nickname,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def add_user(
    email: str,
    password: str,
    nickname: str,
    profile_image_url: str | None = None,
) -> User:
    """새 사용자를 추가합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO user (email, password, nickname, profile_img, terms_agreed_at) VALUES (%s, %s, %s, %s, NOW())",
            (email, password, nickname, profile_image_url),
        )
        user_id = cur.lastrowid

        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise RuntimeError(f"User 생성 직후 조회 실패: user_id={user_id}")
        return _row_to_user(row)


async def update_user(
    user_id: int,
    nickname: str | None = None,
    profile_image_url: str | None = None,
    distro: str | None = None,
) -> User | None:
    """사용자 정보를 업데이트합니다."""
    updates = []
    params = []

    if nickname is not None:
        updates.append("nickname = %s")
        params.append(nickname)
    if profile_image_url is not None:
        updates.append("profile_img = %s")
        params.append(profile_image_url)
    if distro is not None:
        if distro == "":
            updates.append("distro = NULL")
        else:
            updates.append("distro = %s")
            params.append(distro)

    if not updates:
        return await get_user_by_id(user_id)

    # SQL Injection 방지: 컬럼명 검증
    for update_clause in updates:
        column_name = update_clause.split(" = ")[0]
        if column_name not in ALLOWED_USER_COLUMNS:
            raise ValueError(f"Invalid column name: {column_name}")

    async with transactional() as cur:
        await cur.execute(
            f"UPDATE user SET {', '.join(updates)} WHERE id = %s AND deleted_at IS NULL",
            (*params, user_id),
        )

        if cur.rowcount == 0:
            return None

        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def update_password(user_id: int, new_password: str) -> User | None:
    """사용자 비밀번호를 업데이트합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET password = %s WHERE id = %s AND deleted_at IS NULL",
            (new_password, user_id),
        )

        if cur.rowcount == 0:
            return None

        await cur.execute(
            f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


def _generate_anonymized_user_data() -> tuple[str, str]:
    """익명화된 이메일과 닉네임을 생성합니다."""
    unique_id = str(uuid.uuid4())
    timestamp = int(time.time())
    anonymized_nickname = f"deleted_{unique_id[:8]}"
    anonymized_email = f"deleted_{unique_id}_{timestamp}@deleted.user"
    return anonymized_email, anonymized_nickname


async def _disconnect_and_anonymize_user(cur, user_id: int, *, set_deleted_at: bool = False) -> User | None:
    """사용자의 연결을 끊고 익명화하는 공통 로직."""
    anonymized_email, anonymized_nickname = _generate_anonymized_user_data()

    # 1. 연결 끊기: 게시글과 댓글의 author_id를 NULL로 설정
    await cur.execute("UPDATE post SET author_id = NULL WHERE author_id = %s", (user_id,))
    await cur.execute("UPDATE comment SET author_id = NULL WHERE author_id = %s", (user_id,))

    # 2. 토큰 무효화: 모든 리프레시 토큰 삭제
    await cur.execute("DELETE FROM refresh_token WHERE user_id = %s", (user_id,))

    # 3. 사용자 익명화
    if set_deleted_at:
        await cur.execute(
            "UPDATE user SET deleted_at = NOW(), email = %s, nickname = %s WHERE id = %s AND deleted_at IS NULL",
            (anonymized_email, anonymized_nickname, user_id),
        )
    else:
        await cur.execute(
            "UPDATE user SET email = %s, nickname = %s WHERE id = %s AND deleted_at IS NOT NULL",
            (anonymized_email, anonymized_nickname, user_id),
        )

    if cur.rowcount == 0:
        return None

    await cur.execute(f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s", (user_id,))
    row = await cur.fetchone()
    return _row_to_user(row) if row else None


async def withdraw_user(user_id: int) -> User | None:
    """회원 탈퇴를 처리합니다. 소프트 삭제를 수행하며, 재가입을 위해 이메일과 닉네임을 익명화합니다."""
    async with transactional() as cur:
        return await _disconnect_and_anonymize_user(cur, user_id, set_deleted_at=True)


async def cleanup_deleted_user(user_id: int) -> User | None:
    """이미 탈퇴 처리되었으나 정보가 남아있는 사용자(Zombie)를 완전 익명화합니다."""
    async with transactional() as cur:
        return await _disconnect_and_anonymize_user(cur, user_id, set_deleted_at=False)


async def update_nickname_set(user_id: int, nickname: str) -> User | None:
    """닉네임을 설정하고 nickname_set=1로 변경합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET nickname = %s, nickname_set = 1 WHERE id = %s AND deleted_at IS NULL",
            (nickname, user_id),
        )
        if cur.rowcount == 0:
            return None
        await cur.execute(f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s", (user_id,))
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def add_social_user(
    email: str | None,
    nickname: str,
    profile_image_url: str | None = None,
) -> User:
    """소셜 로그인으로 사용자를 생성합니다 (password=NULL, email_verified=1, nickname_set=0)."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO user (email, password, nickname, nickname_set, email_verified, profile_img, terms_agreed_at) "
            "VALUES (%s, NULL, %s, 0, 1, %s, NOW())",
            (email, nickname, profile_image_url),
        )
        user_id = cur.lastrowid
        await cur.execute(f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s", (user_id,))
        row = await cur.fetchone()
        if not row:
            raise RuntimeError(f"User 생성 직후 조회 실패: user_id={user_id}")
        return _row_to_user(row)


async def register_user(
    email: str,
    password: str,
    nickname: str,
    profile_image_url: str | None = None,
) -> User:
    """새 사용자를 등록합니다 (중복 처리 및 Zombie 사용자 정리 포함)."""
    from pymysql.err import IntegrityError

    try:
        return await add_user(email, password, nickname, profile_image_url)
    except IntegrityError as e:
        if e.args[0] == 1062:
            deleted_user_email = await get_deleted_user_by_email(email)
            if deleted_user_email:
                await cleanup_deleted_user(deleted_user_email.id)
                try:
                    return await add_user(email, password, nickname, profile_image_url)
                except IntegrityError:
                    raise IntegrityError(1062, f"Duplicate entry for email='{email}'") from None

            deleted_user_nick = await get_deleted_user_by_nickname(nickname)
            if deleted_user_nick:
                await cleanup_deleted_user(deleted_user_nick.id)
                try:
                    return await add_user(email, password, nickname, profile_image_url)
                except IntegrityError:
                    raise IntegrityError(1062, f"Duplicate entry for nickname='{nickname}'") from None

        raise e
