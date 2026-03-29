-- UTF-8 한국어 데이터 정상 삽입을 위한 클라이언트 인코딩 설정
SET NAMES utf8mb4;

-- 유저 테이블
CREATE TABLE IF NOT EXISTS user (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    email_verified TINYINT(1) NOT NULL DEFAULT 0,
    nickname varchar(255) NOT NULL UNIQUE,
    nickname_set TINYINT(1) NOT NULL DEFAULT 1,
    password varchar(2048) NULL,
    profile_img varchar(2048) NULL,
    role ENUM('user','admin') NOT NULL DEFAULT 'user',
    suspended_until TIMESTAMP NULL,
    suspended_reason VARCHAR(500) NULL,
    terms_agreed_at TIMESTAMP NULL,
    distro VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);

-- 리프레시 토큰 테이블 (JWT 인증용)
CREATE TABLE IF NOT EXISTS refresh_token (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 이메일 인증 테이블
CREATE TABLE IF NOT EXISTS email_verification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 카테고리 테이블
CREATE TABLE IF NOT EXISTS category (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200) NULL,
    sort_order INT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 카테고리 시드 데이터
INSERT IGNORE INTO category (name, slug, description, sort_order) VALUES
    ('배포판', 'distro', 'Ubuntu, Fedora, Arch 등 배포판별 토론 공간입니다.', 1),
    ('Q&A', 'qna', '리눅스 트러블슈팅, 설치, 설정 관련 질문과 답변입니다.', 2),
    ('뉴스/소식', 'news', '리눅스 생태계의 최신 소식을 공유합니다.', 3),
    ('프로젝트/쇼케이스', 'showcase', 'dotfiles, 스크립트, 오픈소스 기여를 공유합니다.', 4),
    ('팁/가이드', 'guide', '리눅스 튜토리얼과 How-to 가이드입니다.', 5),
    ('공지사항', 'notice', '관리자 공지사항입니다.', 6);

-- 게시글 테이블
CREATE TABLE IF NOT EXISTS post (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title varchar(255) NOT NULL,
    content TEXT NOT NULL,
    image_url varchar(2048) NULL,
    author_id INT UNSIGNED NULL,
    category_id INT UNSIGNED NULL,
    is_pinned TINYINT(1) NOT NULL DEFAULT 0,
    views INT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    deleted_at TIMESTAMP NULL,
    accepted_answer_id INT UNSIGNED NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES category (id) ON DELETE SET NULL
);

-- 댓글 테이블
CREATE TABLE IF NOT EXISTS comment (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INT UNSIGNED NULL,
    post_id INT UNSIGNED NOT NULL,
    parent_id INT UNSIGNED NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES comment (id) ON DELETE SET NULL
);

-- post.accepted_answer_id FK (comment 테이블 생성 후 추가)
ALTER TABLE post ADD CONSTRAINT fk_post_accepted_answer
    FOREIGN KEY (accepted_answer_id) REFERENCES comment (id) ON DELETE SET NULL;

-- 좋아요 테이블
CREATE TABLE IF NOT EXISTS post_like (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_like (user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);

-- 이미지 로그 테이블
CREATE TABLE IF NOT EXISTS image (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    image_url varchar(2048) NOT NULL,
    type ENUM('profile', 'post') NOT NULL,
    uploader_id INT UNSIGNED NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploader_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 조회수 로그 테이블
CREATE TABLE IF NOT EXISTS post_view_log (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    view_date DATE GENERATED ALWAYS AS (DATE(created_at)) STORED,
    UNIQUE KEY unique_daily_view (user_id, post_id, view_date),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);
    
-- 소셜 계정 연동 테이블
CREATE TABLE IF NOT EXISTS social_account (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    provider ENUM('github') NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    provider_email VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_social (provider, provider_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 게시글 임시저장 테이블
CREATE TABLE IF NOT EXISTS post_draft (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    title VARCHAR(100) NULL,
    content TEXT NULL,
    category_id INT UNSIGNED NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_draft (user_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 알림 설정 테이블 (유형별 on/off)
CREATE TABLE IF NOT EXISTS notification_setting (
    user_id INT UNSIGNED NOT NULL,
    comment_enabled TINYINT(1) NOT NULL DEFAULT 1,
    like_enabled TINYINT(1) NOT NULL DEFAULT 1,
    mention_enabled TINYINT(1) NOT NULL DEFAULT 1,
    follow_enabled TINYINT(1) NOT NULL DEFAULT 1,
    bookmark_enabled TINYINT(1) NOT NULL DEFAULT 1,
    reply_enabled TINYINT(1) NOT NULL DEFAULT 1,
    digest_frequency ENUM('daily', 'weekly', 'off') NOT NULL DEFAULT 'weekly',
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 알림 테이블
CREATE TABLE IF NOT EXISTS notification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    type ENUM('comment', 'like', 'mention', 'follow', 'bookmark', 'reply') NOT NULL,
    post_id INT UNSIGNED NULL,
    comment_id INT UNSIGNED NULL,
    actor_id INT UNSIGNED NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 신고 테이블
CREATE TABLE IF NOT EXISTS report (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    reporter_id INT UNSIGNED NOT NULL,
    target_type ENUM('post','comment') NOT NULL,
    target_id INT UNSIGNED NOT NULL,
    reason ENUM('spam','abuse','inappropriate','other') NOT NULL,
    description TEXT NULL,
    status ENUM('pending','resolved','dismissed') NOT NULL DEFAULT 'pending',
    resolved_by INT UNSIGNED NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_report (reporter_id, target_type, target_id),
    FOREIGN KEY (reporter_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES user (id) ON DELETE SET NULL
);

-- 북마크 테이블
CREATE TABLE IF NOT EXISTS post_bookmark (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_bookmark (user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);

-- 게시글 구독 테이블
CREATE TABLE IF NOT EXISTS post_subscription (
    user_id    INT UNSIGNED NOT NULL,
    post_id    INT UNSIGNED NOT NULL,
    level      ENUM('watching', 'normal', 'muted') NOT NULL DEFAULT 'watching',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE,
    INDEX idx_post_sub_post (post_id, level)
);

-- 댓글 좋아요 테이블
CREATE TABLE IF NOT EXISTS comment_like (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    comment_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_comment_like (user_id, comment_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (comment_id) REFERENCES comment (id) ON DELETE CASCADE
);

-- 사용자 차단 테이블
CREATE TABLE IF NOT EXISTS user_block (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    blocker_id INT UNSIGNED NOT NULL,
    blocked_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_block (blocker_id, blocked_id),
    FOREIGN KEY (blocker_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (blocked_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 팔로우 테이블
CREATE TABLE IF NOT EXISTS user_follow (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    follower_id INT UNSIGNED NOT NULL,
    following_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_follow (follower_id, following_id),
    FOREIGN KEY (follower_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES user(id) ON DELETE CASCADE
);

-- 게시글 이미지 테이블 (다중 이미지)
CREATE TABLE IF NOT EXISTS post_image (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id INT UNSIGNED NOT NULL,
    image_url VARCHAR(2048) NOT NULL,
    sort_order TINYINT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);

-- 투표 테이블
CREATE TABLE IF NOT EXISTS poll (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id INT UNSIGNED NOT NULL UNIQUE,
    question VARCHAR(200) NOT NULL,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE
);

-- 투표 선택지 테이블
CREATE TABLE IF NOT EXISTS poll_option (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    poll_id INT UNSIGNED NOT NULL,
    option_text VARCHAR(100) NOT NULL,
    sort_order TINYINT UNSIGNED DEFAULT 0,
    FOREIGN KEY (poll_id) REFERENCES poll(id) ON DELETE CASCADE
);

-- 투표 참여 테이블
CREATE TABLE IF NOT EXISTS poll_vote (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    poll_id INT UNSIGNED NOT NULL,
    option_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_vote (poll_id, user_id),
    FOREIGN KEY (poll_id) REFERENCES poll(id) ON DELETE CASCADE,
    FOREIGN KEY (option_id) REFERENCES poll_option(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

    -- 태그 테이블
CREATE TABLE IF NOT EXISTS tag (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE,
    description VARCHAR(200) NULL,
    body TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT UNSIGNED NULL,
    INDEX idx_tag_name (name),
    CONSTRAINT fk_tag_updated_by FOREIGN KEY (updated_by) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 게시글-태그 연결 테이블
CREATE TABLE IF NOT EXISTS post_tag (
    post_id INT UNSIGNED NOT NULL,
    tag_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE,
    INDEX idx_post_tag_tag_id (tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

    -- 성능 최적화 인덱스
    -- 1. 인증/리프레시 토큰 (크리티컬)
    CREATE INDEX idx_refresh_token_hash ON refresh_token (token_hash);
    CREATE INDEX idx_refresh_token_user_id ON refresh_token (user_id);
    
    -- 2. 사용자/게시글/댓글 (Soft Delete 필터링)
    CREATE INDEX idx_user_deleted_at ON user (deleted_at);
    
    -- 3. 게시글 목록 조회 (정렬 + 삭제 필터)
    -- deleted_at 우선 필터링 후 created_at 정렬
    CREATE INDEX idx_post_list_optimized ON post (deleted_at, created_at);
    
    -- 4. 댓글 목록 조회 (특정 게시글 + 삭제 필터 + 정렬)
    CREATE INDEX idx_comment_list_optimized ON comment (post_id, deleted_at, created_at);
    
    -- 5. 좋아요 카운트 조회
    CREATE INDEX idx_post_like_post_id ON post_like (post_id);

    -- 6. 대댓글 조회 최적화
    CREATE INDEX idx_comment_parent_id ON comment (parent_id);

    -- 7. 게시글 제목+내용 전문 검색 (한국어 ngram)
    ALTER TABLE post ADD FULLTEXT INDEX ft_post_search (title, content) WITH PARSER ngram;

    -- 8. 이메일 인증 토큰 조회
    CREATE INDEX idx_email_verification_token ON email_verification (token_hash);
    CREATE INDEX idx_email_verification_expires ON email_verification (expires_at);

    -- 9. 알림 목록 조회 (사용자별 안읽은 알림)
    CREATE INDEX idx_notification_user_unread ON notification (user_id, is_read, created_at DESC);

    -- 10. 댓글 작성자별 조회
    CREATE INDEX idx_comment_author ON comment (author_id, created_at DESC);

    -- 11. 좋아요 사용자별 조회
    CREATE INDEX idx_post_like_user ON post_like (user_id, created_at DESC);

    -- 12. 카테고리별 게시글 조회
    CREATE INDEX idx_post_category ON post (category_id, deleted_at, created_at);

    -- 13. 고정 게시글 조회
    CREATE INDEX idx_post_pinned ON post (is_pinned, deleted_at, created_at DESC);

    -- 14. 신고 상태별 조회
    CREATE INDEX idx_report_status ON report (status, created_at DESC);

    -- 15. 신고 대상별 조회
    CREATE INDEX idx_report_target ON report (target_type, target_id, status);

    -- 16. 북마크 인덱스
    CREATE INDEX idx_post_bookmark_post_id ON post_bookmark (post_id);
    CREATE INDEX idx_post_bookmark_user ON post_bookmark (user_id, created_at DESC);

    -- 17. 댓글 좋아요 인덱스
    CREATE INDEX idx_comment_like_comment_id ON comment_like (comment_id);
    CREATE INDEX idx_comment_like_user ON comment_like (user_id, created_at DESC);

    -- 18. 사용자 차단 인덱스
    CREATE INDEX idx_user_block_blocker ON user_block (blocker_id);
    CREATE INDEX idx_user_block_blocked ON user_block (blocked_id);

    -- 19. 팔로우 인덱스
    CREATE INDEX idx_user_follow_follower ON user_follow(follower_id);
    CREATE INDEX idx_user_follow_following ON user_follow(following_id);

    -- 20. 게시글 이미지 인덱스
    CREATE INDEX idx_post_image_post ON post_image (post_id, sort_order);

    -- 21. 정지 사용자 조회
    CREATE INDEX idx_user_suspended ON user (suspended_until);

    -- 21. 투표 인덱스
    CREATE INDEX idx_poll_post ON poll(post_id);
    CREATE INDEX idx_poll_option_poll ON poll_option(poll_id);
    CREATE INDEX idx_poll_vote_poll ON poll_vote(poll_id);
    CREATE INDEX idx_poll_vote_user ON poll_vote(user_id);

    -- 답변 채택 루트 댓글 검증용
    CREATE INDEX idx_comment_post_parent ON comment (post_id, parent_id);

    -- 이메일 다이제스트 비활성 사용자 스캔용
    CREATE INDEX idx_pvl_user_date ON post_view_log (user_id, created_at);

-- DM 대화 테이블
CREATE TABLE IF NOT EXISTS dm_conversation (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    participant1_id INT UNSIGNED NOT NULL,
    participant2_id INT UNSIGNED NOT NULL,
    last_message_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    UNIQUE KEY uq_conversation_pair (participant1_id, participant2_id),
    FOREIGN KEY (participant1_id) REFERENCES user(id),
    FOREIGN KEY (participant2_id) REFERENCES user(id),
    INDEX idx_conv_participant1 (participant1_id, deleted_at, last_message_at DESC),
    INDEX idx_conv_participant2 (participant2_id, deleted_at, last_message_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- DM 메시지 테이블
CREATE TABLE IF NOT EXISTS dm_message (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT UNSIGNED NOT NULL,
    sender_id INT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (conversation_id) REFERENCES dm_conversation(id),
    FOREIGN KEY (sender_id) REFERENCES user(id),
    INDEX idx_msg_conversation (conversation_id, created_at),
    INDEX idx_msg_unread (conversation_id, sender_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 패키지 정보
CREATE TABLE IF NOT EXISTS package (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    homepage_url VARCHAR(500),
    category VARCHAR(50) NOT NULL,
    package_manager VARCHAR(20),
    created_by INT UNSIGNED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES user(id),
    UNIQUE KEY uk_package_name (name)
);

-- 패키지 리뷰 (1유저 1패키지 1리뷰)
CREATE TABLE IF NOT EXISTS package_review (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    package_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    rating TINYINT UNSIGNED NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    UNIQUE KEY uk_package_user (package_id, user_id),
    FOREIGN KEY (package_id) REFERENCES package(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- 위키 페이지 테이블
CREATE TABLE IF NOT EXISTS wiki_page (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL UNIQUE,
    content TEXT NOT NULL,
    author_id INT UNSIGNED NOT NULL,
    last_edited_by INT UNSIGNED NULL,
    views_count INT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user(id),
    FOREIGN KEY (last_edited_by) REFERENCES user(id)
);

-- 위키 페이지 ↔ 태그 연결 테이블
CREATE TABLE IF NOT EXISTS wiki_page_tag (
    wiki_page_id INT UNSIGNED NOT NULL,
    tag_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (wiki_page_id, tag_id),
    FOREIGN KEY (wiki_page_id) REFERENCES wiki_page(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE
);

-- 22. 위키 페이지 인덱스
CREATE INDEX idx_wiki_page_deleted ON wiki_page (deleted_at, created_at);
ALTER TABLE wiki_page ADD FULLTEXT INDEX ft_wiki_search (title, content) WITH PARSER ngram;
CREATE INDEX idx_wiki_page_tag_tag ON wiki_page_tag (tag_id);

-- 추천 피드 점수 테이블 (배치 재계산, 30분 주기)
CREATE TABLE IF NOT EXISTS user_post_score (
    user_id         INT UNSIGNED NOT NULL,
    post_id         INT UNSIGNED NOT NULL,
    affinity_score  FLOAT NOT NULL DEFAULT 0.0,
    hot_score       FLOAT NOT NULL DEFAULT 0.0,
    combined_score  FLOAT NOT NULL DEFAULT 0.0,
    computed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, post_id),
    INDEX idx_ups_user_combined (user_id, combined_score DESC),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ===== Reputation System =====

CREATE TABLE IF NOT EXISTS reputation_event (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS badge_definition (
    id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(50) NOT NULL UNIQUE,
    description       VARCHAR(200) NOT NULL,
    icon              VARCHAR(50) NOT NULL,
    category          ENUM('bronze','silver','gold') NOT NULL,
    trigger_type      VARCHAR(30) NOT NULL,
    trigger_threshold INT NOT NULL,
    points_awarded    INT NOT NULL DEFAULT 0,
    created_at        DATETIME NOT NULL DEFAULT NOW()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_badge (
    id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id   INT UNSIGNED NOT NULL,
    badge_id  INT UNSIGNED NOT NULL,
    earned_at DATETIME NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (badge_id) REFERENCES badge_definition(id),
    UNIQUE KEY uk_user_badge (user_id, badge_id),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trust_level_definition (
    level           TINYINT PRIMARY KEY,
    name            VARCHAR(30) NOT NULL,
    min_reputation  INT NOT NULL,
    description     VARCHAR(200) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_daily_visit (
    user_id    INT UNSIGNED NOT NULL,
    visit_date DATE NOT NULL,
    PRIMARY KEY (user_id, visit_date),
    FOREIGN KEY (user_id) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- user 테이블 평판 컬럼 (신규 환경에서만 실행 — 기존 환경은 Alembic 마이그레이션 사용)
ALTER TABLE user ADD COLUMN reputation_score INT NOT NULL DEFAULT 0;
ALTER TABLE user ADD COLUMN trust_level TINYINT NOT NULL DEFAULT 0;

-- notification ENUM 확장
ALTER TABLE notification MODIFY COLUMN type
    ENUM('comment', 'like', 'mention', 'follow', 'bookmark', 'reply', 'badge_earned', 'level_up')
    NOT NULL;

-- notification_setting 새 컬럼
ALTER TABLE notification_setting ADD COLUMN badge_earned_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE notification_setting ADD COLUMN level_up_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- 신뢰 등급 시드
INSERT IGNORE INTO trust_level_definition (level, name, min_reputation, description) VALUES
(0, 'New User', 0, '기본 읽기/쓰기'),
(1, 'Member', 50, '위키 편집, 댓글 좋아요'),
(2, 'Regular', 200, '태그 생성, 패키지 등록'),
(3, 'Trusted', 1000, '게시글 신고 우선처리'),
(4, 'Leader', 5000, '커뮤니티 모더레이션 보조');

-- 배지 시드 (27개)
INSERT IGNORE INTO badge_definition (name, description, icon, category, trigger_type, trigger_threshold, points_awarded) VALUES
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
('Completionist', '모든 Bronze + Silver 배지를 획득했습니다', 'crown', 'gold', 'badge_count', 19, 100);

