"""comment_models: 댓글 관련 데이터 모델 및 함수 모듈.

주요 개선사항:
- create_comment 함수에 명시적 트랜잭션 적용
- INSERT와 SELECT을 원자적으로 처리
"""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional
from schemas.common import build_author_dict

ALLOWED_COMMENT_SORT_OPTIONS = {"oldest", "latest", "popular"}


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


def _row_to_comment(row: dict) -> Comment:
    """DictCursor 결과를 Comment 객체로 변환합니다.

    SELECT 컬럼 순서: id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id
    """
    return Comment(
        id=row["id"],
        content=row["content"],
        author_id=row["author_id"],
        post_id=row["post_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        parent_id=row.get("parent_id"),
    )


async def get_comment_by_id(comment_id: int) -> Comment | None:
    """ID로 댓글을 조회합니다."""
    async with get_cursor() as cur:
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


async def create_comment(post_id: int, author_id: int, content: str, parent_id: int | None = None) -> Comment:
    """새 댓글을 생성합니다.

    트랜잭션을 사용하여 INSERT와 SELECT을 원자적으로 처리합니다.

    Raises:
        RuntimeError: 삽입 직후 조회 실패 시 (발생하지 않아야 함).
    """
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO comment (content, author_id, post_id, parent_id) VALUES (%s, %s, %s, %s)",
            (content, author_id, post_id, parent_id),
        )
        comment_id = cur.lastrowid

        await cur.execute(
            "SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id "
            "FROM comment WHERE id = %s",
            (comment_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise RuntimeError(
                f"댓글 삽입 직후 조회 실패: comment_id={comment_id}, post_id={post_id}, author_id={author_id}"
            )

        return _row_to_comment(row)


async def update_comment(comment_id: int, content: str) -> Comment | None:
    """댓글을 수정합니다.

    트랜잭션을 사용하여 UPDATE와 SELECT을 원자적으로 처리합니다.
    """
    async with transactional() as cur:
        await cur.execute(
            "UPDATE comment SET content = %s WHERE id = %s AND deleted_at IS NULL",
            (content, comment_id),
        )
        if cur.rowcount == 0:
            return None

        await cur.execute(
            "SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at, parent_id "
            "FROM comment WHERE id = %s",
            (comment_id,),
        )
        row = await cur.fetchone()
        return _row_to_comment(row) if row else None


async def delete_comment(comment_id: int) -> bool:
    """댓글을 삭제합니다. 소프트 삭제를 수행하여 deleted_at을 현재 시간으로 설정합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE comment SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            (comment_id,),
        )
        return cur.rowcount > 0


async def get_comments_with_author(
    post_id: int,
    current_user_id: int | None = None,
    blocked_user_ids: set[int] | None = None,
    comment_sort: str = "oldest",
    accepted_answer_id: int | None = None,
) -> list[dict]:
    """게시글의 댓글 목록을 트리 구조로 반환합니다.

    삭제된 댓글 처리:
    - 대댓글이 있는 삭제된 부모 댓글: is_deleted=True, content=None, author=None
    - 대댓글이 없는 삭제된 댓글: 목록에서 제외
    """
    # 로그인 사용자의 좋아요 상태 벌크 조회 (N+1 방지)
    liked_comment_ids: set[int] = set()
    if current_user_id:
        from modules.post.comment_like_models import get_liked_comment_ids

        liked_comment_ids = await get_liked_comment_ids(current_user_id, post_id)

    async with get_cursor() as cur:
        # 삭제된 댓글도 포함하여 조회 (대댓글이 있는 경우 표시 필요)
        await cur.execute(
            """
                SELECT c.id, c.content, c.created_at, c.updated_at,
                       u.id AS user_id, u.nickname, u.profile_img, u.distro,
                       c.parent_id, c.deleted_at,
                       COALESCE(cl.cnt, 0) AS likes_count,
                       c.author_id
                FROM comment c
                LEFT JOIN user u ON c.author_id = u.id
                LEFT JOIN (
                    SELECT comment_id, COUNT(*) AS cnt
                    FROM comment_like
                    GROUP BY comment_id
                ) cl ON c.id = cl.comment_id
                WHERE c.post_id = %s
                ORDER BY c.created_at ASC
                """,
            (post_id,),
        )
        rows = await cur.fetchall()

        # 1. 모든 댓글을 dict로 변환
        all_comments: dict[int, dict] = {}
        for row in rows:
            comment_id = row["id"]
            is_deleted = row["deleted_at"] is not None
            author_id = row["author_id"]
            all_comments[comment_id] = {
                "comment_id": comment_id,
                "content": None if is_deleted else row["content"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "author": None
                if is_deleted
                else build_author_dict(
                    row["user_id"],
                    row["nickname"],
                    row["profile_img"],
                    row["distro"],
                ),
                "parent_id": row["parent_id"],
                "is_deleted": is_deleted,
                "likes_count": row["likes_count"],
                "is_liked": comment_id in liked_comment_ids,
                "is_accepted": comment_id == accepted_answer_id,
                "author_id": author_id,
                "replies": [],
            }

        # 2. 부모-자식 관계 구성
        root_comments: list[dict] = []
        for comment in all_comments.values():
            parent_id = comment["parent_id"]
            if parent_id is not None and parent_id in all_comments:
                all_comments[parent_id]["replies"].append(comment)
            else:
                root_comments.append(comment)

        # 3. 대댓글이 없는 삭제된 루트 댓글 제거
        root_comments = [c for c in root_comments if not c["is_deleted"] or len(c["replies"]) > 0]

        # 4. 삭제된 대댓글 제거
        for c in root_comments:
            c["replies"] = [r for r in c["replies"] if not r["is_deleted"]]

        # 5. 차단된 사용자 댓글 필터링 (Python 후처리)
        if blocked_user_ids:
            filtered_root: list[dict] = []
            for c in root_comments:
                if c["is_deleted"]:
                    c["replies"] = [r for r in c["replies"] if r.get("author_id") not in blocked_user_ids]
                    if c["replies"]:
                        filtered_root.append(c)
                elif c.get("author_id") not in blocked_user_ids:
                    c["replies"] = [r for r in c["replies"] if r.get("author_id") not in blocked_user_ids]
                    filtered_root.append(c)
            root_comments = filtered_root

        # 6. 루트 댓글 정렬 (대댓글은 항상 시간순 유지)
        if comment_sort == "latest":
            root_comments.reverse()
        elif comment_sort == "popular":
            root_comments.sort(
                key=lambda c: (c["likes_count"], c["created_at"]),
                reverse=True,
            )

        # 7. author_id 키 제거 (API 응답에 불필요)
        for c in root_comments:
            c.pop("author_id", None)
            for r in c.get("replies", []):
                r.pop("author_id", None)

        return root_comments
