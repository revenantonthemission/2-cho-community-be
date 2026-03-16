-- 알림 설정 테이블 추가
-- 기존 사용자는 행이 없으면 모두 활성화(기본값)로 처리
CREATE TABLE IF NOT EXISTS notification_setting (
    user_id INT UNSIGNED NOT NULL,
    comment_enabled TINYINT(1) NOT NULL DEFAULT 1,
    like_enabled TINYINT(1) NOT NULL DEFAULT 1,
    mention_enabled TINYINT(1) NOT NULL DEFAULT 1,
    follow_enabled TINYINT(1) NOT NULL DEFAULT 1,
    bookmark_enabled TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);
