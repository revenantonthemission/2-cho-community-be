"""user_models: 사용자 관련 데이터 모델 및 함수 모듈.

사용자 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional


@dataclass(frozen=True)
class User:
    """사용자 데이터 클래스.

    Attributes:
        id: 사용자 고유 식별자.
        email: 이메일 주소.
        password: 비밀번호.
        nickname: 닉네임.
        profile_image_url: 프로필 이미지 URL.
        created_at: 생성 시간.
        updated_at: 수정 시간.
        deleted_at: 탈퇴 시간.
    """

    id: int
    email: str
    password: str
    nickname: str
    profile_image_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """사용자가 활성화 상태인지 확인합니다."""
        return self.deleted_at is None

    @property
    def profileImageUrl(self) -> str:
        """프로필 이미지 URL을 반환합니다 (하위 호환성)."""
        # 실제 파일이 assets/profiles/default_profile.jpg 에 위치함
        return self.profile_image_url or "/assets/profiles/default_profile.jpg"


def _row_to_user(row: tuple) -> User:
    """데이터베이스 행을 User 객체로 변환합니다.

    Args:
        row: (id, email, nickname, password, profile_img, created_at, updated_at, deleted_at)

    Returns:
        User 객체.
    """
    return User(
        id=row[0],
        email=row[1],
        nickname=row[2],
        password=row[3],
        profile_image_url=row[4],
        created_at=row[5],
        updated_at=row[6],
        deleted_at=row[7],
    )


async def get_users() -> list[User]:
    """모든 활성 사용자 목록을 반환합니다.

    Returns:
        활성 사용자 목록.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img, 
                       created_at, updated_at, deleted_at
                FROM user
                WHERE deleted_at IS NULL
                ORDER BY id
                """
            )
            rows = await cur.fetchall()
            return [_row_to_user(row) for row in rows]


async def get_user_by_id(user_id: int) -> User | None:
    """ID로 사용자를 조회합니다.

    Args:
        user_id: 조회할 사용자의 ID.

    Returns:
        사용자 객체, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE id = %s AND deleted_at IS NULL
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return _row_to_user(row) if row else None


async def get_user_by_email(email: str) -> User | None:
    """이메일로 사용자를 조회합니다.

    Args:
        email: 조회할 이메일 주소.

    Returns:
        사용자 객체, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE email = %s AND deleted_at IS NULL
                """,
                (email,),
            )
            row = await cur.fetchone()
            return _row_to_user(row) if row else None


async def get_deleted_user_by_email(email: str) -> User | None:
    """이메일로 탈퇴한 사용자를 조회합니다.

    Args:
        email: 조회할 이메일 주소.

    Returns:
        사용자 객체, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE email = %s AND deleted_at IS NOT NULL
                """,
                (email,),
            )
            row = await cur.fetchone()
            return _row_to_user(row) if row else None


async def get_user_by_nickname(nickname: str) -> User | None:
    """닉네임으로 사용자를 조회합니다.

    Args:
        nickname: 조회할 닉네임.

    Returns:
        사용자 객체, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE nickname = %s AND deleted_at IS NULL
                """,
                (nickname,),
            )
            row = await cur.fetchone()
            return _row_to_user(row) if row else None


async def get_deleted_user_by_nickname(nickname: str) -> User | None:
    """닉네임으로 탈퇴한 사용자를 조회합니다.

    Args:
        nickname: 조회할 닉네임.

    Returns:
        사용자 객체, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE nickname = %s AND deleted_at IS NOT NULL
                """,
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
    """새 사용자를 추가합니다.

    Args:
        email: 이메일 주소.
        password: 비밀번호.
        nickname: 닉네임.
        profile_image_url: 프로필 이미지 URL.

    Returns:
        생성된 사용자 객체.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user (email, password, nickname, profile_img)
                VALUES (%s, %s, %s, %s)
                """,
                (email, password, nickname, profile_image_url),
            )
            user_id = cur.lastrowid

            # 생성된 사용자 조회
            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE id = %s
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return _row_to_user(row)


async def update_user(
    user_id: int,
    nickname: str | None = None,
    profile_image_url: str | None = None,
) -> User | None:
    """사용자 정보를 업데이트합니다.

    Args:
        user_id: 업데이트할 사용자의 ID.
        nickname: 새 닉네임 (선택).
        profile_image_url: 새 프로필 이미지 URL (선택).

    Returns:
        업데이트된 사용자 객체, 사용자가 없으면 None.
    """
    # 업데이트할 필드 동적 구성
    updates = []
    params = []

    if nickname is not None:
        updates.append("nickname = %s")
        params.append(nickname)
    if profile_image_url is not None:
        updates.append("profile_img = %s")
        params.append(profile_image_url)

    if not updates:
        return await get_user_by_id(user_id)

    params.append(user_id)

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE user
                SET {", ".join(updates)}
                WHERE id = %s AND deleted_at IS NULL
                """,
                tuple(params),
            )

            if cur.rowcount == 0:
                return None

            return await get_user_by_id(user_id)


async def update_password(user_id: int, new_password: str) -> User | None:
    """사용자 비밀번호를 업데이트합니다.

    Args:
        user_id: 업데이트할 사용자의 ID.
        new_password: 새 비밀번호.

    Returns:
        업데이트된 사용자 객체, 사용자가 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE user
                SET password = %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (new_password, user_id),
            )

            if cur.rowcount == 0:
                return None

            return await get_user_by_id(user_id)


async def withdraw_user(user_id: int) -> User | None:
    """회원 탈퇴를 처리합니다.

    소프트 삭제를 수행하며, 재가입을 위해 이메일과 닉네임을 익명화합니다.
    email -> deleted_{uuid}_{timestamp}
    nickname -> deleted_{uuid_prefix}

    Args:
        user_id: 탈퇴할 사용자의 ID.

    Returns:
        탈퇴 처리된 사용자 객체, 사용자가 없으면 None.
    """
    import uuid
    import time

    unique_id = str(uuid.uuid4())
    timestamp = int(time.time())

    # 닉네임 길이 제한(20자) 등을 고려하여 짧게 생성
    # 예: deleted_a1b2c3d4
    anonymized_nickname = f"deleted_{unique_id[:8]}"

    # 이메일은 Unique 유지를 위해 충분히 길게
    anonymized_email = f"deleted_{unique_id}_{timestamp}@deleted.user"

    async with transactional() as cur:
        # 1. Sever links: Set author_id to NULL for posts and comments
        await cur.execute(
            """
            UPDATE post SET author_id = NULL WHERE author_id = %s
            """,
            (user_id,),
        )
        await cur.execute(
            """
            UPDATE comment SET author_id = NULL WHERE author_id = %s
            """,
            (user_id,),
        )

        # 2. Kill sessions: Delete all active sessions
        await cur.execute(
            """
            DELETE FROM user_session WHERE user_id = %s
            """,
            (user_id,),
        )

        # 3. Anonymize user (Soft Delete)
        await cur.execute(
            """
            UPDATE user
            SET deleted_at = NOW(),
                email = %s,
                nickname = %s
            WHERE id = %s AND deleted_at IS NULL
            """,
            (anonymized_email, anonymized_nickname, user_id),
        )

        if cur.rowcount == 0:
            return None

        # 삭제된 사용자 조회 (deleted_at 포함)
        await cur.execute(
            """
            SELECT id, email, nickname, password, profile_img,
                   created_at, updated_at, deleted_at
            FROM user
            WHERE id = %s
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def cleanup_deleted_user(user_id: int) -> User | None:
    """이미 탈퇴 처리되었으나 정보가 남아있는 사용자(Zombie)를 완전 익명화합니다.

    Args:
        user_id: 정리할 사용자의 ID.

    Returns:
        정리된 사용자 객체, 사용자가 없으면 None.
    """
    import uuid
    import time

    unique_id = str(uuid.uuid4())
    timestamp = int(time.time())

    anonymized_nickname = f"deleted_{unique_id[:8]}"
    anonymized_email = f"deleted_{unique_id}_{timestamp}@deleted.user"

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # 1. Sever links for zombie
            await cur.execute(
                """
                UPDATE post SET author_id = NULL WHERE author_id = %s
                """,
                (user_id,),
            )
            await cur.execute(
                """
                UPDATE comment SET author_id = NULL WHERE author_id = %s
                """,
                (user_id,),
            )

            # 2. Kill sessions for zombie
            await cur.execute(
                """
                DELETE FROM user_session WHERE user_id = %s
                """,
                (user_id,),
            )

            # 3. Anonymize user
            await cur.execute(
                """
                UPDATE user
                SET email = %s,
                nickname = %s
                WHERE id = %s
                """,
                (anonymized_email, anonymized_nickname, user_id),
            )

            if cur.rowcount == 0:
                return None

            await cur.execute(
                """
                SELECT id, email, nickname, password, profile_img,
                       created_at, updated_at, deleted_at
                FROM user
                WHERE id = %s
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return _row_to_user(row) if row else None


async def create_session(user_id: int, session_id: str, expires_at: datetime) -> None:
    """사용자 세션을 생성합니다.

    Args:
        user_id: 사용자 ID.
        session_id: 세션 ID.
        expires_at: 만료 시간.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_session (user_id, session_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, session_id, expires_at),
            )


async def get_session(session_id: str) -> dict | None:
    """세션 ID로 세션 정보를 조회합니다.

    Args:
        session_id: 세션 ID.

    Returns:
        세션 정보 딕셔너리, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, user_id, session_id, expires_at
                FROM user_session
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = await cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "session_id": row[2],
                    "expires_at": row[3],
                }
            return None


async def delete_session(session_id: str) -> None:
    """세션을 삭제합니다.

    Args:
        session_id: 세션 ID.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM user_session WHERE session_id = %s
                """,
                (session_id,),
            )
