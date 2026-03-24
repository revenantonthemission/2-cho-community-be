-- 투표 시스템 마이그레이션

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

-- 투표 인덱스
CREATE INDEX idx_poll_post ON poll(post_id);
CREATE INDEX idx_poll_option_poll ON poll_option(poll_id);
CREATE INDEX idx_poll_vote_poll ON poll_vote(poll_id);
CREATE INDEX idx_poll_vote_user ON poll_vote(user_id);
