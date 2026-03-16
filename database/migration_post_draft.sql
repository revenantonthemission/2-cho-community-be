-- 게시글 임시저장 테이블 추가 (사용자당 최대 1개)
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
