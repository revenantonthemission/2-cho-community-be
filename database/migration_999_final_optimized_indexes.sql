-- [FINAL MIGRATION] 기존 DB를 위한 인덱스 추가
-- 이미 존재하는 인덱스는 무시됩니다 (Duplicate key name 에러 발생 시 해당 인덱스는 이미 있음)
-- 참고: 이 스크립트는 mysql 클라이언트에서 직접 실행하거나 --force 옵션과 함께 실행하세요:
-- mysql -u root community_service --force < database/migration_999_final_optimized_indexes.sql

-- 1. 세션 조회 성능 (크리티컬 - 모든 인증에 영향)
CREATE INDEX idx_user_session_session_id ON user_session (session_id (255));

-- 2. Soft Delete 필터링 인덱스
CREATE INDEX idx_user_deleted_at ON user (deleted_at);

-- 3. 게시글 목록 최적화 (deleted_at 필터 + created_at 정렬)
CREATE INDEX idx_post_list_optimized ON post (deleted_at, created_at);

-- 4. 댓글 목록 최적화 (post_id 필터 + deleted_at 필터 + created_at 정렬)
CREATE INDEX idx_comment_list_optimized ON comment (
    post_id,
    deleted_at,
    created_at
);

-- 5. 좋아요 조회 최적화
CREATE INDEX idx_post_like_post_id ON post_like (post_id);