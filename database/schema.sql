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

-- 유저 세션 테이블
CREATE TABLE user_session (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    session_id varchar(2048) NOT NULL,
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
    author_id INT UNSIGNED NOT NULL,
    views INT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE CASCADE
);

-- 댓글 테이블
CREATE TABLE comment (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INT UNSIGNED NOT NULL,
    post_id INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE CASCADE,
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
    view_date DATE GENERATED ALWAYS AS (DATE(created_at)) VIRTUAL,
    UNIQUE KEY unique_view_daily (user_id, post_id, view_date),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES post (id) ON DELETE CASCADE
);