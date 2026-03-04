-- 계정 정지 기능 마이그레이션

ALTER TABLE user
    ADD COLUMN suspended_until TIMESTAMP NULL AFTER role,
    ADD COLUMN suspended_reason VARCHAR(500) NULL AFTER suspended_until;

CREATE INDEX idx_user_suspended ON user (suspended_until);
