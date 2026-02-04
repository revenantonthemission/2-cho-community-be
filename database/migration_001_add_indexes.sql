-- =====================================================
-- 성능 개선 인덱스 마이그레이션
-- 실행: mysql -u [user] -p [database] < migration_001_add_indexes.sql
-- =====================================================

-- 1. 세션 조회 성능 (크리티컬 - 모든 인증에 영향)
CREATE INDEX idx_user_session_session_id ON user_session (session_id(255));

-- 2. Soft Delete 쿼리 최적화
CREATE INDEX idx_user_deleted_at ON user (deleted_at);

CREATE INDEX idx_post_deleted_at ON post (deleted_at);

CREATE INDEX idx_comment_deleted_at ON comment (deleted_at);

-- 3. 댓글/좋아요 조회 최적화
CREATE INDEX idx_comment_post_id ON comment (post_id);

CREATE INDEX idx_post_like_post_id ON post_like (post_id);

-- 검증
-- EXPLAIN SELECT * FROM user_session WHERE session_id = 'test';