-- 이용약관 동의 기록 컬럼 추가
-- 기존 사용자는 NULL (동의 기록 없음), 신규 가입자는 NOW()로 설정
ALTER TABLE user ADD COLUMN terms_agreed_at TIMESTAMP NULL AFTER suspended_reason;

-- 기존 사용자에 대해 가입 시점을 동의 시점으로 소급 적용 (선택사항)
-- UPDATE user SET terms_agreed_at = created_at WHERE terms_agreed_at IS NULL;
