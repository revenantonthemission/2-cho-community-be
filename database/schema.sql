-- 유저 테이블
CREATE TABLE user (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    nickname varchar(255) NOT NULL UNIQUE,
    password varchar(2048) NOT NULL,
    profile_img varchar(2048) NULL,
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

-- 게시글 테이블
CREATE TABLE post (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title varchar(255) NOT NULL,
    content TEXT NOT NULL,
    image_url varchar(2048) NULL,
    author_id INT UNSIGNED NULL,
    views INT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL
);

-- 댓글 테이블
CREATE TABLE comment (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INT UNSIGNED NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
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
    