"""user_models: 사용자 관련 데이터 모델 및 함수 모듈.

사용자 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional


# SQL Injection 방지: 허용된 컬럼명 whitelist
ALLOWED_USER_COLUMNS = {'nickname', 'profile_img'}


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


# 공통으로 사용되는 SELECT 필드
USER_SELECT_FIELDS = (
    "id, email, nickname, password, profile_img, created_at, updated_at, deleted_at"
)


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
                f"""
                SELECT {USER_SELECT_FIELDS}
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
                f"""
                SELECT {USER_SELECT_FIELDS}
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
                f"""
                SELECT {USER_SELECT_FIELDS}
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
                f"""
                SELECT {USER_SELECT_FIELDS}
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
                f"""
                SELECT {USER_SELECT_FIELDS}
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
    async with transactional() as cur:
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
            f"""
            SELECT {USER_SELECT_FIELDS}
            FROM user
            WHERE id = %s
            """,
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

    # SQL Injection 방지: 컬럼명 검증
    for update_clause in updates:
        column_name = update_clause.split(' = ')[0]
        if column_name not in ALLOWED_USER_COLUMNS:
            raise ValueError(f"Invalid column name: {column_name}")

    async with transactional() as cur:
        await cur.execute(
            f"""
            UPDATE user
            SET {", ".join(updates)}
            WHERE id = %s AND deleted_at IS NULL
            """,
            (*params, user_id),
        )

        if cur.rowcount == 0:
            return None

        # 같은 트랜잭션 내에서 수정된 사용자 조회
        await cur.execute(
            f"""
            SELECT {USER_SELECT_FIELDS}
            FROM user
            WHERE id = %s
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


async def update_password(user_id: int, new_password: str) -> User | None:
    """사용자 비밀번호를 업데이트합니다.

    Args:
        user_id: 업데이트할 사용자의 ID.
        new_password: 새 비밀번호.

    Returns:
        업데이트된 사용자 객체, 사용자가 없으면 None.
    """
    async with transactional() as cur:
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

        # 같은 트랜잭션 내에서 수정된 사용자 조회
        await cur.execute(
            f"""
            SELECT {USER_SELECT_FIELDS}
            FROM user
            WHERE id = %s
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return _row_to_user(row) if row else None


def _generate_anonymized_user_data() -> tuple[str, str]:
    """익명화된 이메일과 닉네임을 생성합니다.

    Returns:
        (email, nickname) 튜플
    """
    unique_id = str(uuid.uuid4())
    timestamp = int(time.time())

    # 닉네임 길이 제한(20자) 등을 고려하여 짧게 생성
    anonymized_nickname = f"deleted_{unique_id[:8]}"

    # 이메일은 Unique 유지를 위해 충분히 길게
    anonymized_email = f"deleted_{unique_id}_{timestamp}@deleted.user"

    return anonymized_email, anonymized_nickname


async def _disconnect_and_anonymize_user(
    cur, user_id: int, *, set_deleted_at: bool = False
) -> User | None:
    """사용자의 연결을 끊고 익명화하는 공통 로직.

    게시글/댓글의 author_id를 NULL로 설정하고, 리프레시 토큰을 삭제하며,
    이메일과 닉네임을 익명화합니다.

    Args:
        cur: 트랜잭션 커서.
        user_id: 처리할 사용자의 ID.
        set_deleted_at: True이면 deleted_at을 NOW()로 설정하고
                        deleted_at IS NULL 조건으로 필터링합니다.

    Returns:
        처리된 사용자 객체, 사용자가 없으면 None.
    """
    anonymized_email, anonymized_nickname = _generate_anonymized_user_data()

    # 1. 연결 끊기: 게시글과 댓글의 author_id를 NULL로 설정
    await cur.execute(
        "UPDATE post SET author_id = NULL WHERE author_id = %s",
        (user_id,),
    )
    await cur.execute(
        "UPDATE comment SET author_id = NULL WHERE author_id = %s",
        (user_id,),
    )

    # 2. 토큰 무효화: 모든 리프레시 토큰 삭제
    await cur.execute(
        "DELETE FROM refresh_token WHERE user_id = %s",
        (user_id,),
    )

    # 3. 사용자 익명화
    if set_deleted_at:
        await cur.execute(
            """
            UPDATE user
            SET deleted_at = NOW(), email = %s, nickname = %s
            WHERE id = %s AND deleted_at IS NULL
            """,
            (anonymized_email, anonymized_nickname, user_id),
        )
    else:
        await cur.execute(
            """
            UPDATE user
            SET email = %s, nickname = %s
            WHERE id = %s
            """,
            (anonymized_email, anonymized_nickname, user_id),
        )

    if cur.rowcount == 0:
        return None

    await cur.execute(
        f"SELECT {USER_SELECT_FIELDS} FROM user WHERE id = %s",
        (user_id,),
    )
    row = await cur.fetchone()
    return _row_to_user(row) if row else None


async def withdraw_user(user_id: int) -> User | None:
    """회원 탈퇴를 처리합니다.

    소프트 삭제를 수행하며, 재가입을 위해 이메일과 닉네임을 익명화합니다.

    Args:
        user_id: 탈퇴할 사용자의 ID.

    Returns:
        탈퇴 처리된 사용자 객체, 사용자가 없으면 None.
    """
    async with transactional() as cur:
        return await _disconnect_and_anonymize_user(cur, user_id, set_deleted_at=True)


async def cleanup_deleted_user(user_id: int) -> User | None:
    """이미 탈퇴 처리되었으나 정보가 남아있는 사용자(Zombie)를 완전 익명화합니다.

    Args:
        user_id: 정리할 사용자의 ID.

    Returns:
        정리된 사용자 객체, 사용자가 없으면 None.
    """
    async with transactional() as cur:
        return await _disconnect_and_anonymize_user(cur, user_id, set_deleted_at=False)


__all__ = [
    "User",
]


async def register_user(
    email: str,
    password: str,
    nickname: str,
    profile_image_url: str | None = None,
) -> User:
    """새 사용자를 등록합니다 (중복 처리 및 Zombie 사용자 정리 포함).

    이메일이나 닉네임이 중복되는 경우:
    1. 탈퇴한 사용자(Zombie)인지 확인합니다.
    2. Zombie라면 정보를 익명화하여 정리합니다.
    3. 사용자 생성을 재시도합니다.
    4. 재시도 실패 시 IntegrityError를 발생시킵니다.

    Args:
        email: 이메일 주소.
        password: 비밀번호.
        nickname: 닉네임.
        profile_image_url: 프로필 이미지 URL.

    Returns:
        생성된 사용자 객체.

    Raises:
        IntegrityError: 중복된 이메일/닉네임이며 Zombie가 아닌 경우, 또는 재시도 실패 시.
    """
    from pymysql.err import IntegrityError

    try:
        return await add_user(email, password, nickname, profile_image_url)
    except IntegrityError as e:
        # 중복 엔트리 에러 (1062)
        if e.args[0] == 1062:
            # 1. 이메일이 탈퇴한 사용자의 것인지 확인
            deleted_user_email = await get_deleted_user_by_email(email)
            if deleted_user_email:
                await cleanup_deleted_user(deleted_user_email.id)
                try:
                    return await add_user(email, password, nickname, profile_image_url)
                except IntegrityError:
                    # cleanup과 add_user 사이에 동시 요청이 선점한 경우
                    raise IntegrityError(1062, f"Duplicate entry for email='{email}'")

            # 2. 닉네임이 탈퇴한 사용자의 것인지 확인
            deleted_user_nick = await get_deleted_user_by_nickname(nickname)
            if deleted_user_nick:
                await cleanup_deleted_user(deleted_user_nick.id)
                try:
                    return await add_user(email, password, nickname, profile_image_url)
                except IntegrityError:
                    # cleanup과 add_user 사이에 동시 요청이 선점한 경우
                    raise IntegrityError(
                        1062, f"Duplicate entry for nickname='{nickname}'"
                    )

        # 좀비 사용자가 아니거나 다른 IntegrityError
        raise e
