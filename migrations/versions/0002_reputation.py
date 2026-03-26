"""평판 시스템 테이블 + user/notification 컬럼 확장.

5개 신규 테이블: reputation_event, badge_definition, user_badge,
trust_level_definition, user_daily_visit.
기존 테이블 변경: user(reputation_score, trust_level),
notification(type ENUM 확장), notification_setting(badge_earned_enabled, level_up_enabled).
시드 데이터: trust_level_definition(5행), badge_definition(27행).

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-26
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. 신규 테이블 생성 (reputation_event 존재 여부로 일괄 판단)
    # ------------------------------------------------------------------
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'reputation_event'"
        )
    )
    tables_exist = bool(result.scalar())

    if not tables_exist:
        conn.execute(
            text("""
            CREATE TABLE reputation_event (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id         INT UNSIGNED NOT NULL,
                event_type      VARCHAR(30) NOT NULL,
                points          INT NOT NULL,
                source_user_id  INT UNSIGNED NULL,
                source_type     VARCHAR(20) NULL,
                source_id       INT UNSIGNED NULL,
                is_backfill     BOOLEAN NOT NULL DEFAULT FALSE,
                created_at      DATETIME NOT NULL DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (source_user_id) REFERENCES user(id),
                INDEX idx_user_created (user_id, created_at),
                INDEX idx_source (source_type, source_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        )

        conn.execute(
            text("""
            CREATE TABLE badge_definition (
                id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                name              VARCHAR(50) NOT NULL UNIQUE,
                description       VARCHAR(200) NOT NULL,
                icon              VARCHAR(50) NOT NULL,
                category          ENUM('bronze','silver','gold') NOT NULL,
                trigger_type      VARCHAR(30) NOT NULL,
                trigger_threshold INT NOT NULL,
                points_awarded    INT NOT NULL DEFAULT 0,
                created_at        DATETIME NOT NULL DEFAULT NOW()
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        )

        conn.execute(
            text("""
            CREATE TABLE user_badge (
                id        BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id   INT UNSIGNED NOT NULL,
                badge_id  INT UNSIGNED NOT NULL,
                earned_at DATETIME NOT NULL DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (badge_id) REFERENCES badge_definition(id),
                UNIQUE KEY uk_user_badge (user_id, badge_id),
                INDEX idx_user (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        )

        conn.execute(
            text("""
            CREATE TABLE trust_level_definition (
                level           TINYINT PRIMARY KEY,
                name            VARCHAR(30) NOT NULL,
                min_reputation  INT NOT NULL,
                description     VARCHAR(200) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        )

        conn.execute(
            text("""
            CREATE TABLE user_daily_visit (
                user_id    INT UNSIGNED NOT NULL,
                visit_date DATE NOT NULL,
                PRIMARY KEY (user_id, visit_date),
                FOREIGN KEY (user_id) REFERENCES user(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        )

        # 시드 데이터: 신뢰 등급
        conn.execute(
            text("""
            INSERT INTO trust_level_definition (level, name, min_reputation, description) VALUES
            (0, 'New User', 0, '기본 읽기/쓰기'),
            (1, 'Member', 50, '위키 편집, 댓글 좋아요'),
            (2, 'Regular', 200, '태그 생성, 패키지 등록'),
            (3, 'Trusted', 1000, '게시글 신고 우선처리'),
            (4, 'Leader', 5000, '커뮤니티 모더레이션 보조')
        """)
        )

        # 시드 데이터: 배지 정의 (27개)
        conn.execute(
            text("""
            INSERT INTO badge_definition (name, description, icon, category, trigger_type, trigger_threshold, points_awarded) VALUES
            ('First Post', '첫 번째 게시글을 작성했습니다', 'edit', 'bronze', 'post_count', 1, 5),
            ('First Comment', '첫 번째 댓글을 작성했습니다', 'comment', 'bronze', 'comment_count', 1, 5),
            ('First Like', '첫 번째 좋아요를 눌렀습니다', 'heart', 'bronze', 'like_given_count', 1, 2),
            ('Welcome', '프로필을 완성했습니다 (아바타 + 배포판)', 'user-check', 'bronze', 'profile_completed', 1, 5),
            ('Bookworm', '첫 번째 북마크를 추가했습니다', 'bookmark', 'bronze', 'bookmark_count', 1, 2),
            ('Curious', '10개의 게시글을 조회했습니다', 'eye', 'bronze', 'post_view_count', 10, 2),
            ('Supporter', '10개의 좋아요를 눌렀습니다', 'thumbs-up', 'bronze', 'like_given_count', 10, 5),
            ('Editor', '첫 번째 위키 페이지를 편집했습니다', 'file-text', 'bronze', 'wiki_edit_count', 1, 5),
            ('Reviewer', '첫 번째 패키지 리뷰를 작성했습니다', 'star', 'bronze', 'package_review_count', 1, 5),
            ('Messenger', '첫 번째 DM을 보냈습니다', 'message-circle', 'bronze', 'dm_sent_count', 1, 2),
            ('Prolific', '50개의 게시글을 작성했습니다', 'edit-3', 'silver', 'post_count', 50, 20),
            ('Commenter', '100개의 댓글을 작성했습니다', 'message-square', 'silver', 'comment_count', 100, 20),
            ('Helpful Answer', '10개의 답변이 채택되었습니다', 'check-circle', 'silver', 'accepted_answer_count', 10, 30),
            ('Nice Question', '하나의 게시글이 10개의 좋아요를 받았습니다', 'award', 'silver', 'single_post_likes', 10, 20),
            ('Popular Question', '하나의 게시글이 100회 조회되었습니다', 'trending-up', 'silver', 'single_post_views', 100, 20),
            ('Wiki Contributor', '20개의 위키 페이지를 편집했습니다', 'book-open', 'silver', 'wiki_edit_count', 20, 20),
            ('Socializer', '25명의 팔로워를 모았습니다', 'users', 'silver', 'follower_count', 25, 15),
            ('Devoted', '14일 연속 방문했습니다', 'calendar', 'silver', 'consecutive_visit_days', 14, 20),
            ('Package Critic', '10개의 패키지 리뷰를 작성했습니다', 'package', 'silver', 'package_review_count', 10, 15),
            ('Legendary', '평판 점수 5000을 달성했습니다', 'zap', 'gold', 'reputation_score', 5000, 100),
            ('Great Answer', '하나의 답변이 50개의 좋아요를 받았습니다', 'shield', 'gold', 'single_comment_likes', 50, 50),
            ('Famous Question', '하나의 게시글이 1000회 조회되었습니다', 'globe', 'gold', 'single_post_views', 1000, 50),
            ('Mentor', '100개의 답변이 채택되었습니다', 'award', 'gold', 'accepted_answer_count', 100, 100),
            ('Wiki Master', '100개의 위키 페이지를 편집했습니다', 'book', 'gold', 'wiki_edit_count', 100, 50),
            ('Dedicated', '60일 연속 방문했습니다', 'sunrise', 'gold', 'consecutive_visit_days', 60, 50),
            ('Community Pillar', '100명의 팔로워를 모았습니다', 'flag', 'gold', 'follower_count', 100, 50),
            ('Completionist', '모든 Bronze + Silver 배지를 획득했습니다', 'crown', 'gold', 'badge_count', 19, 100)
        """)
        )

    # ------------------------------------------------------------------
    # 2. 기존 테이블 ALTER (항상 실행, 멱등성 보장)
    # ------------------------------------------------------------------

    # user 테이블: reputation_score 컬럼 추가
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'user' "
            "AND column_name = 'reputation_score'"
        )
    )
    if not result.scalar():
        conn.execute(text("ALTER TABLE user ADD COLUMN reputation_score INT NOT NULL DEFAULT 0"))

    # user 테이블: trust_level 컬럼 추가
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'user' "
            "AND column_name = 'trust_level'"
        )
    )
    if not result.scalar():
        conn.execute(text("ALTER TABLE user ADD COLUMN trust_level TINYINT NOT NULL DEFAULT 0"))

    # notification 테이블: type ENUM 확장 (badge_earned, level_up 추가)
    conn.execute(
        text("""
        ALTER TABLE notification MODIFY COLUMN type
            ENUM('comment', 'like', 'mention', 'follow', 'bookmark', 'reply', 'badge_earned', 'level_up')
            NOT NULL
    """)
    )

    # notification_setting 테이블: badge_earned_enabled 컬럼 추가
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'notification_setting' "
            "AND column_name = 'badge_earned_enabled'"
        )
    )
    if not result.scalar():
        conn.execute(
            text("ALTER TABLE notification_setting ADD COLUMN badge_earned_enabled BOOLEAN NOT NULL DEFAULT TRUE")
        )

    # notification_setting 테이블: level_up_enabled 컬럼 추가
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'notification_setting' "
            "AND column_name = 'level_up_enabled'"
        )
    )
    if not result.scalar():
        conn.execute(text("ALTER TABLE notification_setting ADD COLUMN level_up_enabled BOOLEAN NOT NULL DEFAULT TRUE"))


def downgrade() -> None:
    conn = op.get_bind()

    # notification_setting 컬럼 제거
    conn.execute(text("ALTER TABLE notification_setting DROP COLUMN IF EXISTS level_up_enabled"))
    conn.execute(text("ALTER TABLE notification_setting DROP COLUMN IF EXISTS badge_earned_enabled"))

    # notification type ENUM 축소 전, 새 타입 행 삭제 (데이터 절단 방지)
    conn.execute(text("DELETE FROM notification WHERE type IN ('badge_earned', 'level_up')"))

    # notification type ENUM 원복
    conn.execute(
        text("""
        ALTER TABLE notification MODIFY COLUMN type
            ENUM('comment', 'like', 'mention', 'follow', 'bookmark', 'reply')
            NOT NULL
    """)
    )

    # user 컬럼 제거
    conn.execute(text("ALTER TABLE user DROP COLUMN IF EXISTS trust_level"))
    conn.execute(text("ALTER TABLE user DROP COLUMN IF EXISTS reputation_score"))

    # 신규 테이블 삭제 (FK 순서: 자식 → 부모)
    conn.execute(text("DROP TABLE IF EXISTS user_daily_visit"))
    conn.execute(text("DROP TABLE IF EXISTS user_badge"))
    conn.execute(text("DROP TABLE IF EXISTS reputation_event"))
    conn.execute(text("DROP TABLE IF EXISTS trust_level_definition"))
    conn.execute(text("DROP TABLE IF EXISTS badge_definition"))
