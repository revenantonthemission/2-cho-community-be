"""affinity_models: 추천 피드를 위한 사용자 신호 수집 및 점수 저장 모듈."""

from dataclasses import dataclass, field

from database.connection import get_connection, transactional


@dataclass
class UserSignals:
    """사용자 상호작용 신호 데이터."""

    liked_tag_counts: dict[int, int] = field(default_factory=dict)
    bookmarked_tag_counts: dict[int, int] = field(default_factory=dict)
    commented_tag_counts: dict[int, int] = field(default_factory=dict)
    viewed_category_counts: dict[int, int] = field(default_factory=dict)
    followed_author_ids: set[int] = field(default_factory=set)
    liked_author_counts: dict[int, int] = field(default_factory=dict)
    bookmarked_author_counts: dict[int, int] = field(default_factory=dict)


async def get_user_signals(user_id: int, lookback_days: int = 30) -> UserSignals:
    """사용자의 최근 상호작용 신호를 수집합니다.

    Args:
        user_id: 사용자 ID.
        lookback_days: 과거 N일 내 활동만 수집.

    Returns:
        UserSignals 데이터.
    """
    signals = UserSignals()
    async with get_connection() as conn, conn.cursor() as cur:
        # 1. 좋아요한 게시글의 태그
        await cur.execute(
            """
                SELECT pt.tag_id, COUNT(*) AS cnt
                FROM post_like pl
                INNER JOIN post_tag pt ON pl.post_id = pt.post_id
                WHERE pl.user_id = %s
                  AND pl.created_at > NOW() - INTERVAL %s DAY
                GROUP BY pt.tag_id
                """,
            (user_id, lookback_days),
        )
        for row in await cur.fetchall():
            signals.liked_tag_counts[row[0]] = row[1]

        # 2. 북마크한 게시글의 태그
        await cur.execute(
            """
                SELECT pt.tag_id, COUNT(*) AS cnt
                FROM post_bookmark pb
                INNER JOIN post_tag pt ON pb.post_id = pt.post_id
                WHERE pb.user_id = %s
                  AND pb.created_at > NOW() - INTERVAL %s DAY
                GROUP BY pt.tag_id
                """,
            (user_id, lookback_days),
        )
        for row in await cur.fetchall():
            signals.bookmarked_tag_counts[row[0]] = row[1]

        # 3. 댓글 단 게시글의 태그
        await cur.execute(
            """
                SELECT pt.tag_id, COUNT(*) AS cnt
                FROM comment c
                INNER JOIN post_tag pt ON c.post_id = pt.post_id
                WHERE c.author_id = %s AND c.deleted_at IS NULL
                  AND c.created_at > NOW() - INTERVAL %s DAY
                GROUP BY pt.tag_id
                """,
            (user_id, lookback_days),
        )
        for row in await cur.fetchall():
            signals.commented_tag_counts[row[0]] = row[1]

        # 4. 조회한 게시글의 카테고리
        await cur.execute(
            """
                SELECT p.category_id, COUNT(*) AS cnt
                FROM post_view_log pvl
                INNER JOIN post p ON pvl.post_id = p.id AND p.deleted_at IS NULL
                WHERE pvl.user_id = %s AND p.category_id IS NOT NULL
                  AND pvl.created_at > NOW() - INTERVAL %s DAY
                GROUP BY p.category_id
                """,
            (user_id, lookback_days),
        )
        for row in await cur.fetchall():
            signals.viewed_category_counts[row[0]] = row[1]

        # 5. 팔로우한 작성자
        await cur.execute(
            "SELECT following_id FROM user_follow WHERE follower_id = %s",
            (user_id,),
        )
        signals.followed_author_ids = {row[0] for row in await cur.fetchall()}

        # 6. 좋아요한 게시글의 작성자
        await cur.execute(
            """
                SELECT p.author_id, COUNT(*) AS cnt
                FROM post_like pl
                INNER JOIN post p ON pl.post_id = p.id
                WHERE pl.user_id = %s AND p.author_id IS NOT NULL
                  AND pl.created_at > NOW() - INTERVAL %s DAY
                GROUP BY p.author_id
                """,
            (user_id, lookback_days),
        )
        for row in await cur.fetchall():
            signals.liked_author_counts[row[0]] = row[1]

        # 7. 북마크한 게시글의 작성자
        await cur.execute(
            """
                SELECT p.author_id, COUNT(*) AS cnt
                FROM post_bookmark pb
                INNER JOIN post p ON pb.post_id = p.id
                WHERE pb.user_id = %s AND p.author_id IS NOT NULL
                  AND pb.created_at > NOW() - INTERVAL %s DAY
                GROUP BY p.author_id
                """,
            (user_id, lookback_days),
        )
        for row in await cur.fetchall():
            signals.bookmarked_author_counts[row[0]] = row[1]

    return signals


async def get_active_user_ids(lookback_days: int = 30) -> list[int]:
    """최근 활동한 사용자 ID 목록을 반환합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT DISTINCT user_id FROM (
                    SELECT user_id FROM post_view_log
                    WHERE created_at > NOW() - INTERVAL %s DAY
                    UNION
                    SELECT user_id FROM post_like
                    WHERE created_at > NOW() - INTERVAL %s DAY
                    UNION
                    SELECT user_id FROM post_bookmark
                    WHERE created_at > NOW() - INTERVAL %s DAY
                    UNION
                    SELECT author_id AS user_id FROM comment
                    WHERE deleted_at IS NULL
                      AND created_at > NOW() - INTERVAL %s DAY
                ) active_users
                """,
            (lookback_days, lookback_days, lookback_days, lookback_days),
        )
        return [row[0] for row in await cur.fetchall()]


async def get_candidate_posts_meta(max_age_days: int = 7) -> list[dict]:
    """추천 후보 게시글의 메타데이터를 벌크 조회합니다.

    Returns:
        각 게시글의 post_id, category_id, author_id, hot_score, tag_ids.
    """
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT
                    p.id,
                    p.category_id,
                    p.author_id,
                    (COALESCE(lk.cnt, 0) * 3
                     + COALESCE(cm.cnt, 0) * 2
                     + p.views * 0.5)
                    / POW(TIMESTAMPDIFF(HOUR, p.created_at, NOW()) + 2, 1.5)
                    AS hot_score
                FROM post p
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM post_like GROUP BY post_id
                ) lk ON p.id = lk.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM comment WHERE deleted_at IS NULL GROUP BY post_id
                ) cm ON p.id = cm.post_id
                WHERE p.deleted_at IS NULL
                  AND p.created_at > NOW() - INTERVAL %s DAY
                """,
            (max_age_days,),
        )
        posts = []
        for row in await cur.fetchall():
            posts.append(
                {
                    "post_id": row[0],
                    "category_id": row[1],
                    "author_id": row[2],
                    "hot_score": float(row[3]) if row[3] else 0.0,
                }
            )

        # 태그 벌크 조회
        if posts:
            post_ids = [p["post_id"] for p in posts]
            placeholders = ", ".join(["%s"] * len(post_ids))
            await cur.execute(
                f"""
                    SELECT post_id, tag_id
                    FROM post_tag
                    WHERE post_id IN ({placeholders})
                    """,
                post_ids,
            )
            tag_map: dict[int, list[int]] = {}
            for row in await cur.fetchall():
                tag_map.setdefault(row[0], []).append(row[1])
            for p in posts:
                p["tag_ids"] = tag_map.get(p["post_id"], [])
        else:
            for p in posts:
                p["tag_ids"] = []

        return posts


async def upsert_user_post_scores(
    user_id: int,
    rows: list[dict],
) -> int:
    """user_post_score 테이블에 점수를 배치 UPSERT합니다.

    Args:
        user_id: 사용자 ID.
        rows: [{"post_id": int, "affinity_score": float, "hot_score": float, "combined_score": float}]

    Returns:
        기록된 행 수.
    """
    if not rows:
        return 0

    chunk_size = 500
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        values_sql = ", ".join(["(%s, %s, %s, %s, %s)"] * len(chunk))
        params: list = []
        for r in chunk:
            params.extend(
                [
                    user_id,
                    r["post_id"],
                    r["affinity_score"],
                    r["hot_score"],
                    r["combined_score"],
                ]
            )

        async with transactional() as cur:
            await cur.execute(
                f"""
                INSERT INTO user_post_score
                    (user_id, post_id, affinity_score, hot_score, combined_score)
                VALUES {values_sql}
                ON DUPLICATE KEY UPDATE
                    affinity_score = VALUES(affinity_score),
                    hot_score = VALUES(hot_score),
                    combined_score = VALUES(combined_score)
                """,
                params,
            )
            total += cur.rowcount

    return total


async def delete_stale_scores(user_id: int, valid_post_ids: set[int]) -> int:
    """해당 사용자의 후보 목록에 없는 오래된 점수를 삭제합니다."""
    if not valid_post_ids:
        # 후보가 없으면 해당 사용자의 모든 점수 삭제
        async with transactional() as cur:
            await cur.execute(
                "DELETE FROM user_post_score WHERE user_id = %s",
                (user_id,),
            )
            return cur.rowcount

    placeholders = ", ".join(["%s"] * len(valid_post_ids))
    async with transactional() as cur:
        await cur.execute(
            f"""
            DELETE FROM user_post_score
            WHERE user_id = %s AND post_id NOT IN ({placeholders})
            """,
            [user_id, *valid_post_ids],
        )
        return cur.rowcount


async def user_has_scores(user_id: int) -> bool:
    """사용자의 추천 점수가 존재하는지 확인합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM user_post_score WHERE user_id = %s LIMIT 1",
            (user_id,),
        )
        return await cur.fetchone() is not None
