-- 유저 테이블
CREATE TABLE user (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    email_verified TINYINT(1) NOT NULL DEFAULT 0,
    nickname varchar(255) NOT NULL UNIQUE,
    password varchar(2048) NOT NULL,
    profile_img varchar(2048) NULL,
    role ENUM('user','admin') NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);

-- 리프레시 토큰 테이블 (JWT 인증용)
CREATE TABLE refresh_token (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 이메일 인증 테이블
CREATE TABLE email_verification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 카테고리 테이블
CREATE TABLE category (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200) NULL,
    sort_order INT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 카테고리 시드 데이터
INSERT INTO category (name, slug, description, sort_order) VALUES
    ('자유게시판', 'free', '자유롭게 이야기하는 공간입니다.', 1),
    ('질문답변', 'qna', '궁금한 것을 질문하고 답변합니다.', 2),
    ('정보공유', 'info', '유용한 정보를 공유합니다.', 3),
    ('공지사항', 'notice', '관리자 공지사항입니다.', 4);

-- 게시글 테이블
CREATE TABLE post (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title varchar(255) NOT NULL,
    content TEXT NOT NULL,
    image_url varchar(2048) NULL,
    author_id INT UNSIGNED NULL,
    category_id INT UNSIGNED NULL,
    is_pinned TINYINT(1) NOT NULL DEFAULT 0,
    views INT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES category (id) ON DELETE SET NULL
);

-- 댓글 테이블
CREATE TABLE comment (
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

-- 좋아요 테이블
CREATE TABLE post_like (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_like (user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);

-- 이미지 로그 테이블
CREATE TABLE image (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    image_url varchar(2048) NOT NULL,
    type ENUM('profile', 'post') NOT NULL,
    uploader_id INT UNSIGNED NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploader_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 조회수 로그 테이블
CREATE TABLE post_view_log (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    view_date DATE GENERATED ALWAYS AS (DATE(created_at)) STORED,
    UNIQUE KEY unique_daily_view (user_id, post_id, view_date),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);
    
-- 알림 테이블
CREATE TABLE notification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    type ENUM('comment', 'like') NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    comment_id INT UNSIGNED NULL,
    actor_id INT UNSIGNED NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 신고 테이블
CREATE TABLE report (
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

