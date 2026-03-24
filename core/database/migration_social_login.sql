-- 소셜 로그인 DB 스키마 마이그레이션

-- 1. user.password NULL 허용 (소셜 로그인 사용자는 비밀번호 없음)
ALTER TABLE user MODIFY COLUMN password VARCHAR(2048) NULL;

-- 2. 닉네임 설정 여부 플래그 (소셜 로그인 후 닉네임 미설정 상태 추적)
ALTER TABLE user ADD COLUMN nickname_set TINYINT(1) NOT NULL DEFAULT 1 AFTER nickname;

-- 3. 소셜 계정 연동 테이블
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
