"""기존 데이터 기반 평판 소급 백필 스크립트.

사용법: cd 2-cho-community-be && uv run python scripts/backfill_reputation.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import close_db, get_cursor, init_db, transactional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def backfill_from_query(label: str, query: str, event_type: str, points: int) -> int:
    """배치 단위로 소스 테이블을 스캔하여 평판 이벤트를 백필합니다."""
    total = 0
    last_id = 0
    while True:
        async with get_cursor() as cur:
            await cur.execute(query + " AND t.id > %s ORDER BY t.id LIMIT %s", (last_id, BATCH_SIZE))
            rows = await cur.fetchall()
        if not rows:
            break
        async with transactional() as cur:
            for row in rows:
                await cur.execute(
                    "INSERT INTO reputation_event "
                    "(user_id, event_type, points, source_user_id, source_type, source_id, is_backfill, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)",
                    (
                        row["user_id"],
                        event_type,
                        points,
                        row.get("source_user_id"),
                        row.get("source_type"),
                        row.get("source_id"),
                        row["created_at"],
                    ),
                )
                last_id = row["id"]
        total += len(rows)
        logger.info("  %s: %d행 처리됨 (누적 %d)", label, len(rows), total)
    return total


async def backfill_post_likes() -> int:
    """post_like → post_liked 이벤트 백필 (+10, 게시글 작성자에게)."""
    query = (
        "SELECT t.id, p.author_id AS user_id, t.user_id AS source_user_id, "
        "'post' AS source_type, t.post_id AS source_id, t.created_at "
        "FROM post_like t "
        "JOIN post p ON t.post_id = p.id "
        "WHERE p.author_id IS NOT NULL AND p.deleted_at IS NULL"
    )
    return await backfill_from_query("post_like → post_liked", query, "post_liked", 10)


async def backfill_comment_likes() -> int:
    """comment_like → comment_liked 이벤트 백필 (+5, 댓글 작성자에게)."""
    query = (
        "SELECT t.id, c.author_id AS user_id, t.user_id AS source_user_id, "
        "'comment' AS source_type, t.comment_id AS source_id, t.created_at "
        "FROM comment_like t "
        "JOIN comment c ON t.comment_id = c.id "
        "WHERE c.author_id IS NOT NULL AND c.deleted_at IS NULL"
    )
    return await backfill_from_query("comment_like → comment_liked", query, "comment_liked", 5)


async def backfill_posts() -> int:
    """post → post_created 이벤트 백필 (+5, 게시글 작성자에게)."""
    query = (
        "SELECT t.id, t.author_id AS user_id, NULL AS source_user_id, "
        "'post' AS source_type, t.id AS source_id, t.created_at "
        "FROM post t "
        "WHERE t.author_id IS NOT NULL AND t.deleted_at IS NULL"
    )
    return await backfill_from_query("post → post_created", query, "post_created", 5)


async def backfill_comments() -> int:
    """comment → comment_created 이벤트 백필 (+2, 댓글 작성자에게)."""
    query = (
        "SELECT t.id, t.author_id AS user_id, NULL AS source_user_id, "
        "'comment' AS source_type, t.id AS source_id, t.created_at "
        "FROM comment t "
        "WHERE t.author_id IS NOT NULL AND t.deleted_at IS NULL"
    )
    return await backfill_from_query("comment → comment_created", query, "comment_created", 2)


async def backfill_wiki_pages() -> int:
    """wiki_page → wiki_created 이벤트 백필 (+20, 작성자에게)."""
    query = (
        "SELECT t.id, t.author_id AS user_id, NULL AS source_user_id, "
        "'wiki_page' AS source_type, t.id AS source_id, t.created_at "
        "FROM wiki_page t "
        "WHERE t.author_id IS NOT NULL"
    )
    return await backfill_from_query("wiki_page → wiki_created", query, "wiki_created", 20)


async def backfill_package_reviews() -> int:
    """package_review → package_review_created 이벤트 백필 (+15, 리뷰어에게)."""
    query = (
        "SELECT t.id, t.user_id AS user_id, NULL AS source_user_id, "
        "'package_review' AS source_type, t.id AS source_id, t.created_at "
        "FROM package_review t "
        "WHERE t.user_id IS NOT NULL"
    )
    return await backfill_from_query("package_review → package_review_created", query, "package_review_created", 15)


async def backfill_accepted_answers() -> int:
    """채택된 답변 → answer_accepted 이벤트 백필 (+50, 댓글 작성자에게).

    채택 답변은 통상 소량이므로 배치 없이 단건 처리합니다.
    """
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT c.id, c.author_id AS user_id, p.author_id AS source_user_id, "
            "'post' AS source_type, c.post_id AS source_id, c.created_at "
            "FROM comment c "
            "JOIN post p ON c.post_id = p.id "
            "WHERE c.is_accepted = TRUE AND c.author_id IS NOT NULL AND c.deleted_at IS NULL"
        )
        rows = await cur.fetchall()

    if not rows:
        logger.info("  accepted_answer: 대상 행 없음")
        return 0

    async with transactional() as cur:
        for row in rows:
            await cur.execute(
                "INSERT INTO reputation_event "
                "(user_id, event_type, points, source_user_id, source_type, source_id, is_backfill, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)",
                (
                    row["user_id"],
                    "answer_accepted",
                    50,
                    row.get("source_user_id"),
                    row.get("source_type"),
                    row.get("source_id"),
                    row["created_at"],
                ),
            )

    logger.info("  accepted_answer: %d행 처리됨", len(rows))
    return len(rows)


async def recompute_reputation_scores() -> None:
    """모든 사용자의 reputation_score를 reputation_event 합계로 재계산합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user u SET reputation_score = "
            "COALESCE((SELECT SUM(points) FROM reputation_event WHERE user_id = u.id), 0) "
            "WHERE u.deleted_at IS NULL"
        )
    logger.info("reputation_score 재계산 완료")


async def recompute_trust_levels() -> None:
    """모든 사용자의 trust_level을 trust_level_definition 기준으로 재계산합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user u SET trust_level = "
            "COALESCE(("
            "  SELECT tl.level FROM trust_level_definition tl "
            "  WHERE tl.min_reputation <= u.reputation_score "
            "  ORDER BY tl.level DESC LIMIT 1"
            "), 0) WHERE u.deleted_at IS NULL"
        )
    logger.info("trust_level 재계산 완료")


async def evaluate_badges() -> None:
    """모든 사용자에 대해 배지 조건을 평가합니다."""
    from modules.reputation.service import ReputationService

    async with get_cursor() as cur:
        await cur.execute("SELECT id FROM user WHERE deleted_at IS NULL")
        users = await cur.fetchall()

    badge_event_types = [
        "post_created",
        "comment_created",
        "post_liked",
        "comment_liked",
        "post_like_given",
        "answer_accepted",
        "wiki_created",
        "package_review_created",
        "reputation_changed",
    ]

    for i, u in enumerate(users):
        for event_type in badge_event_types:
            await ReputationService._check_badges(u["id"], event_type, None, None)
        if (i + 1) % 100 == 0:
            logger.info("  %d/%d 사용자 배지 평가 완료", i + 1, len(users))

    logger.info("배지 평가 완료 (총 %d명)", len(users))


async def main() -> None:
    """소급 백필 전체 흐름을 실행합니다."""
    await init_db()
    try:
        logger.info("=== 평판 소급 백필 시작 ===")

        # 1. post_like → post_liked (+10)
        logger.info("[1/7] 게시글 좋아요 백필")
        n = await backfill_post_likes()
        logger.info("  완료: %d건", n)

        # 2. comment_like → comment_liked (+5)
        logger.info("[2/7] 댓글 좋아요 백필")
        n = await backfill_comment_likes()
        logger.info("  완료: %d건", n)

        # 3. post → post_created (+5)
        logger.info("[3/7] 게시글 작성 백필")
        n = await backfill_posts()
        logger.info("  완료: %d건", n)

        # 4. comment → comment_created (+2)
        logger.info("[4/7] 댓글 작성 백필")
        n = await backfill_comments()
        logger.info("  완료: %d건", n)

        # 5. wiki_page → wiki_created (+20)
        logger.info("[5/7] 위키 페이지 작성 백필")
        n = await backfill_wiki_pages()
        logger.info("  완료: %d건", n)

        # 6. package_review → package_review_created (+15)
        logger.info("[6/7] 패키지 리뷰 작성 백필")
        n = await backfill_package_reviews()
        logger.info("  완료: %d건", n)

        # 7. 채택된 답변 → answer_accepted (+50)
        logger.info("[7/7] 채택된 답변 백필")
        n = await backfill_accepted_answers()
        logger.info("  완료: %d건", n)

        # 8. reputation_score 재계산
        logger.info("[8/10] reputation_score 벌크 재계산")
        await recompute_reputation_scores()

        # 9. trust_level 재계산
        logger.info("[9/10] trust_level 벌크 재계산")
        await recompute_trust_levels()

        # 10. 배지 평가
        logger.info("[10/10] 전체 사용자 배지 평가")
        await evaluate_badges()

        logger.info("=== 백필 완료 ===")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
