"""comment_models: 댓글 관련 데이터 모델 및 함수 모듈.

주요 개선사항:
- create_comment 함수에 명시적 트랜잭션 적용
- INSERT와 SELECT을 원자적으로 처리
"""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional
from schemas.common import build_author_dict


@dataclass
class Comment:
    """댓글 데이터 클래스.

    Attributes:
        id: 댓글 고유 식별자.
        post_id: 게시글 ID.
        author_id: 작성자 ID.
        content: 내용.
        created_at: 생성 시간.
        updated_at: 수정 시간.
        deleted_at: 삭제 시간.
        parent_id: 부모 댓글 ID (대댓글인 경우).
    """

    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    parent_id: int | None = None

    @property
    def is_deleted(self) -> bool:
        """댓글이 삭제되었는지 확인합니다."""
        return self.deleted_at is not None


def _row_to_comment(row: tuple) -> Comment:
    """데이터베이스 행을 Comment 객체로 변환합니다."""
    return Comment(
        id=row[0],
        content=row[1],
        author_id=row[2],
        post_id=row[3],
        created_at=row[4],
        updated_at=row[5],
        deleted_at=row[6],
        parent_id=row[7] if len(row) > 7 else None,
    )


async def get_comments_by_post(post_id: int) -> list[Comment]:
    """특정 게시글의 댓글 목록을 조회합니다.

    삭제되지 않은 댓글을 작성순으로 정렬하여 반환합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        댓글 목록.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id
                FROM comment
                WHERE post_id = %s AND deleted_at IS NULL
                ORDER BY created_at ASC
                """,
                (post_id,),
            )
            rows = await cur.fetchall()
            return [_row_to_comment(row) for row in rows]


async def get_comments_count_by_post(post_id: int) -> int:
    """특정 게시글의 댓글 수를 조회합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        댓글 수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM comment
                WHERE post_id = %s AND deleted_at IS NULL
                """,
                (post_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_comment_by_id(comment_id: int) -> Comment | None:
    """ID로 댓글을 조회합니다.

    Args:
        comment_id: 조회할 댓글 ID.

    Returns:
        댓글 객체, 없거나 삭제된 경우 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id
                FROM comment
                WHERE id = %s AND deleted_at IS NULL
                """,
                (comment_id,),
            )
            row = await cur.fetchone()
            return _row_to_comment(row) if row else None


async def create_comment(
    post_id: int, author_id: int, content: str, parent_id: int | None = None
) -> Comment:
    """새 댓글을 생성합니다.

    트랜잭션을 사용하여 INSERT와 SELECT을 원자적으로 처리합니다.

    Args:
        post_id: 게시글 ID.
        author_id: 작성자 ID.
        content: 내용.
        parent_id: 부모 댓글 ID (대댓글인 경우).

    Returns:
        생성된 댓글 객체.

    Raises:
        RuntimeError: 삽입 직후 조회 실패 시 (발생하지 않아야 함).
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO comment (content, author_id, post_id, parent_id)
            VALUES (%s, %s, %s, %s)
            """,
            (content, author_id, post_id, parent_id),
        )
        comment_id = cur.lastrowid

        # 같은 트랜잭션 내에서 조회
        await cur.execute(
            """
            SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id
            FROM comment
            WHERE id = %s
            """,
            (comment_id,),
        )
        row = await cur.fetchone()

        # 삽입 직후 조회 실패는 발생하지 않아야 함
        if not row:
            raise RuntimeError(
                f"댓글 삽입 직후 조회 실패: comment_id={comment_id}, "
                f"post_id={post_id}, author_id={author_id}"
            )

        return _row_to_comment(row)


async def update_comment(comment_id: int, content: str) -> Comment | None:
    """댓글을 수정합니다.

    트랜잭션을 사용하여 UPDATE와 SELECT을 원자적으로 처리합니다.

    Args:
        comment_id: 수정할 댓글 ID.
        content: 새 내용.

    Returns:
        수정된 댓글 객체, 없거나 삭제된 경우 None.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE comment
            SET content = %s
            WHERE id = %s AND deleted_at IS NULL
            """,
            (content, comment_id),
        )

        if cur.rowcount == 0:
            return None

        # 같은 트랜잭션 내에서 수정된 댓글 조회
        await cur.execute(
            """
            SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id
            FROM comment
            WHERE id = %s
            """,
            (comment_id,),
        )
        row = await cur.fetchone()
        return _row_to_comment(row) if row else None


async def delete_comment(comment_id: int) -> bool:
    """댓글을 삭제합니다.

    소프트 삭제를 수행하여 deleted_at을 현재 시간으로 설정합니다.

    Args:
        comment_id: 삭제할 댓글 ID.

    Returns:
        삭제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE comment
            SET deleted_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            """,
            (comment_id,),
        )
        return cur.rowcount > 0


async def get_comments_with_author(post_id: int) -> list[dict]:
    """게시글의 댓글 목록을 트리 구조로 반환합니다.

    삭제된 댓글 처리:
    - 대댓글이 있는 삭제된 부모 댓글: is_deleted=True, content=None, author=None
    - 대댓글이 없는 삭제된 댓글: 목록에서 제외

    Args:
        post_id: 게시글 ID.

    Returns:
        루트 댓글 목록 (각 댓글에 replies 리스트 포함).
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # 삭제된 댓글도 포함하여 조회 (대댓글이 있는 경우 표시 필요)
            await cur.execute(
                """
                SELECT c.id, c.content, c.created_at, c.updated_at,
                       u.id, u.nickname, u.profile_img,
                       c.parent_id, c.deleted_at
                FROM comment c
                LEFT JOIN user u ON c.author_id = u.id
                WHERE c.post_id = %s
                ORDER BY c.created_at ASC
                """,
                (post_id,),
            )
            rows = await cur.fetchall()

            # 1. 모든 댓글을 dict로 변환
            all_comments: dict[int, dict] = {}
            for row in rows:
                comment_id = row[0]
                is_deleted = row[8] is not None
                all_comments[comment_id] = {
                    "comment_id": comment_id,
                    "content": None if is_deleted else row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "author": None if is_deleted else build_author_dict(row[4], row[5], row[6]),
                    "parent_id": row[7],
                    "is_deleted": is_deleted,
                    "replies": [],
                }

            # 2. 부모-자식 관계 구성
            root_comments: list[dict] = []
            for comment in all_comments.values():
                parent_id = comment["parent_id"]
                if parent_id is not None and parent_id in all_comments:
                    all_comments[parent_id]["replies"].append(comment)
                else:
                    # parent_id가 None이거나 부모가 조회 결과에 없는 경우(고아 댓글) 루트로 처리
                    root_comments.append(comment)

            # 3. 대댓글이 없는 삭제된 루트 댓글 제거
            root_comments = [
                c for c in root_comments
                if not c["is_deleted"] or len(c["replies"]) > 0
            ]

            # 4. 삭제된 대댓글 제거 (1단계 제한으로 하위 댓글 불가)
            for c in root_comments:
                c["replies"] = [r for r in c["replies"] if not r["is_deleted"]]

            return root_comments
