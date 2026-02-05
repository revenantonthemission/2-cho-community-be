-- 게시글 목록 조회 성능 향상을 위한 복합 인덱스
-- 사용 쿼리: SELECT ... FROM post WHERE deleted_at IS NULL ORDER BY created_at DESC
CREATE INDEX idx_post_list ON post (deleted_at, created_at);

-- 댓글 목록 조회 성능 향상을 위한 복합 인덱스
-- 사용 쿼리: SELECT ... FROM comment WHERE post_id = ? AND deleted_at IS NULL ORDER BY created_at ASC
CREATE INDEX idx_comment_list ON comment (post_id, deleted_at, created_at);
