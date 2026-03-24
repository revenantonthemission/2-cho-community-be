-- 추천 피드 (For You Feed) 마이그레이션
-- 사용자별 게시글 추천 점수 테이블 (배치 재계산, 30분 주기)

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
