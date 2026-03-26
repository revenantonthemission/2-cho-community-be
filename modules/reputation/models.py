"""reputation.models: 평판 시스템 관련 데이터 모델 및 쿼리 함수 모음."""

from datetime import date, timedelta

from pymysql.err import IntegrityError

from core.database.connection import get_cursor, transactional

# ---------------------------------------------------------------------------
# 평판 이벤트
# ---------------------------------------------------------------------------


async def insert_reputation_event(
    user_id: int,
    event_type: str,
    points: int,
    source_user_id: int | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    is_backfill: bool = False,
) -> int:
    """평판 이벤트를 삽입하고 생성된 레코드 ID를 반환합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO reputation_event
                (user_id, event_type, points, source_user_id, source_type, source_id, is_backfill)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, event_type, points, source_user_id, source_type, source_id, is_backfill),
        )
        return cur.lastrowid  # type: ignore[return-value]


async def get_reputation_history(user_id: int, offset: int = 0, limit: int = 20) -> list[dict]:
    """사용자의 평판 이벤트 히스토리를 최신순으로 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT id, user_id, event_type, points, source_user_id,
                   source_type, source_id, is_backfill, created_at
            FROM reputation_event
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()
        return list(rows)


async def get_reputation_history_count(user_id: int) -> int:
    """사용자의 평판 이벤트 총 개수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM reputation_event WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def find_original_event(
    user_id: int,
    event_type: str,
    source_type: str,
    source_id: int,
) -> dict | None:
    """취소(revocation)를 위해 가장 최근 양의 포인트 이벤트를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT id, user_id, event_type, points, source_user_id,
                   source_type, source_id, is_backfill, created_at
            FROM reputation_event
            WHERE user_id = %s
              AND event_type = %s
              AND source_type = %s
              AND source_id = %s
              AND points > 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, event_type, source_type, source_id),
        )
        return await cur.fetchone()


# ---------------------------------------------------------------------------
# 사용자 평판 점수 / 신뢰 등급
# ---------------------------------------------------------------------------


async def update_user_reputation(user_id: int, delta: int) -> None:
    """사용자의 평판 점수를 delta만큼 증감합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET reputation_score = reputation_score + %s WHERE id = %s",
            (delta, user_id),
        )


async def get_user_reputation_score(user_id: int) -> int:
    """사용자의 현재 평판 점수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT reputation_score FROM user WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["reputation_score"] if row else 0


async def get_user_trust_level(user_id: int) -> int:
    """사용자의 현재 신뢰 등급을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT trust_level FROM user WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["trust_level"] if row else 0


async def update_user_trust_level(user_id: int, new_level: int) -> bool:
    """신뢰 등급이 실제로 변경된 경우에만 UPDATE하고 True를 반환합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET trust_level = %s WHERE id = %s AND trust_level != %s",
            (new_level, user_id, new_level),
        )
        return cur.rowcount > 0  # type: ignore[return-value]


async def get_user_reputation_summary(user_id: int) -> dict | None:
    """사용자 평판 요약 정보(평판 점수, 신뢰 등급 정보, 배지 수)를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.id AS user_id,
                u.reputation_score,
                u.trust_level,
                tld.name AS trust_level_name,
                tld.description AS trust_level_description,
                tld.min_reputation,
                (SELECT COUNT(*) FROM user_badge ub WHERE ub.user_id = u.id) AS badge_count
            FROM user u
            LEFT JOIN trust_level_definition tld ON u.trust_level = tld.level
            WHERE u.id = %s
            """,
            (user_id,),
        )
        return await cur.fetchone()


# ---------------------------------------------------------------------------
# 신뢰 등급 정의
# ---------------------------------------------------------------------------


async def get_trust_level_definitions() -> list[dict]:
    """모든 신뢰 등급 정의를 레벨 오름차순으로 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT level, name, min_reputation, description FROM trust_level_definition ORDER BY level ASC"
        )
        rows = await cur.fetchall()
        return list(rows)


async def get_appropriate_trust_level(reputation_score: int) -> int:
    """평판 점수에 적합한 신뢰 등급을 계산하여 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT level
            FROM trust_level_definition
            WHERE min_reputation <= %s
            ORDER BY level DESC
            LIMIT 1
            """,
            (reputation_score,),
        )
        row = await cur.fetchone()
        return row["level"] if row else 0


# ---------------------------------------------------------------------------
# 배지 정의
# ---------------------------------------------------------------------------


async def get_all_badge_definitions() -> list[dict]:
    """모든 배지 정의를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT id, name, description, icon, category,
                   trigger_type, trigger_threshold, points_awarded, created_at
            FROM badge_definition
            ORDER BY id ASC
            """
        )
        rows = await cur.fetchall()
        return list(rows)


async def get_badge_definitions_by_trigger(trigger_type: str) -> list[dict]:
    """특정 trigger_type에 해당하는 배지 정의 목록을 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT id, name, description, icon, category,
                   trigger_type, trigger_threshold, points_awarded, created_at
            FROM badge_definition
            WHERE trigger_type = %s
            ORDER BY trigger_threshold ASC
            """,
            (trigger_type,),
        )
        rows = await cur.fetchall()
        return list(rows)


async def get_user_badges(user_id: int) -> list[dict]:
    """사용자가 획득한 배지 목록을 배지 정의와 JOIN하여 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT ub.id, ub.user_id, ub.badge_id, ub.earned_at,
                   bd.name, bd.description, bd.icon, bd.category,
                   bd.trigger_type, bd.trigger_threshold, bd.points_awarded
            FROM user_badge ub
            JOIN badge_definition bd ON ub.badge_id = bd.id
            WHERE ub.user_id = %s
            ORDER BY ub.earned_at DESC
            """,
            (user_id,),
        )
        rows = await cur.fetchall()
        return list(rows)


async def get_user_badge_count(user_id: int) -> int:
    """사용자가 획득한 배지 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_badge WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def award_badge(user_id: int, badge_id: int) -> bool:
    """배지를 수여합니다. 이미 획득한 배지이면 False를 반환합니다."""
    try:
        async with transactional() as cur:
            await cur.execute(
                "INSERT INTO user_badge (user_id, badge_id) VALUES (%s, %s)",
                (user_id, badge_id),
            )
        return True
    except IntegrityError as e:
        if e.args[0] == 1062:  # 중복 키
            return False
        raise


# ---------------------------------------------------------------------------
# 배지 체크용 집계 쿼리
# ---------------------------------------------------------------------------


async def count_user_posts(user_id: int) -> int:
    """사용자가 작성한 게시글 수를 반환합니다 (소프트 삭제 제외)."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM post WHERE author_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_comments(user_id: int) -> int:
    """사용자가 작성한 댓글 수를 반환합니다 (소프트 삭제 제외)."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM comment WHERE author_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_likes_given(user_id: int) -> int:
    """사용자가 누른 좋아요 수를 반환합니다 (게시글 + 댓글 합산)."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM post_like WHERE user_id = %s)
                + (SELECT COUNT(*) FROM comment_like WHERE user_id = %s)
                AS cnt
            """,
            (user_id, user_id),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_bookmarks(user_id: int) -> int:
    """사용자가 추가한 북마크 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM post_bookmark WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_accepted_answers(user_id: int) -> int:
    """사용자의 댓글이 채택된 답변 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM post p
            JOIN comment c ON p.accepted_answer_id = c.id
            WHERE c.author_id = %s
              AND c.deleted_at IS NULL
              AND p.deleted_at IS NULL
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_wiki_edits(user_id: int) -> int:
    """사용자의 위키 편집/생성 이벤트 수를 반환합니다 (양의 포인트 이벤트 기준)."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM reputation_event
            WHERE user_id = %s
              AND event_type IN ('wiki_created', 'wiki_edited')
              AND points > 0
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_package_reviews(user_id: int) -> int:
    """사용자가 작성한 패키지 리뷰 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM package_review WHERE user_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_dm_sent(user_id: int) -> int:
    """사용자가 전송한 DM 수를 반환합니다 (소프트 삭제 제외)."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM dm_message WHERE sender_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_user_followers(user_id: int) -> int:
    """사용자의 팔로워 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_follow WHERE following_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_single_post_likes(post_id: int) -> int:
    """특정 게시글의 좋아요 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM post_like WHERE post_id = %s",
            (post_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def count_single_comment_likes(comment_id: int) -> int:
    """특정 댓글의 좋아요 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM comment_like WHERE comment_id = %s",
            (comment_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def get_post_views(post_id: int) -> int:
    """특정 게시글의 조회수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT views FROM post WHERE id = %s",
            (post_id,),
        )
        row = await cur.fetchone()
        return row["views"] if row else 0


async def count_user_post_views(user_id: int) -> int:
    """사용자가 조회한 고유 게시글 수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(DISTINCT post_id) AS cnt FROM post_view_log WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# 프로필 완성도 + 방문 연속일
# ---------------------------------------------------------------------------


async def is_profile_completed(user_id: int) -> bool:
    """사용자의 프로필이 완성되었는지 확인합니다 (아바타 + 배포판 모두 설정 필요)."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT profile_img, distro FROM user WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False
        return bool(row["profile_img"]) and bool(row["distro"])


async def record_daily_visit(user_id: int) -> bool:
    """오늘의 방문을 기록합니다. 이미 기록된 경우 False를 반환합니다."""
    today = date.today()
    try:
        async with transactional() as cur:
            await cur.execute(
                "INSERT INTO user_daily_visit (user_id, visit_date) VALUES (%s, %s)",
                (user_id, today),
            )
        return True
    except IntegrityError as e:
        if e.args[0] == 1062:  # 중복 키
            return False
        raise


async def get_consecutive_visit_days(user_id: int) -> int:
    """오늘 또는 어제부터 연속 방문 일수를 계산합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
            SELECT visit_date
            FROM user_daily_visit
            WHERE user_id = %s
            ORDER BY visit_date DESC
            LIMIT 365
            """,
            (user_id,),
        )
        rows = await cur.fetchall()

    if not rows:
        return 0

    # 날짜 집합으로 변환
    visit_dates: set[date] = {row["visit_date"] for row in rows}

    today = date.today()
    # 오늘 또는 어제부터 스트릭 시작
    if today in visit_dates:
        current = today
    elif (today - timedelta(days=1)) in visit_dates:
        current = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while current in visit_dates:
        streak += 1
        current -= timedelta(days=1)

    return streak
