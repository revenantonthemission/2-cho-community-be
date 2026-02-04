-- deleted_at 컬럼에 대한 인덱스 추가
-- 모든 조회 쿼리가 deleted_at IS NULL을 포함하므로 성능 향상에 필수적임

CREATE INDEX idx_user_deleted_at ON user(deleted_at);
CREATE INDEX idx_post_deleted_at ON post(deleted_at);
CREATE INDEX idx_comment_deleted_at ON comment(deleted_at);

-- 댓글 조회 시 post_id와 함께 필터링하므로 복합 인덱스 추가
CREATE INDEX idx_comment_post_deleted ON comment(post_id, deleted_at);

-- 게시글 목록 조회 시 최신순 정렬을 위한 복합 인덱스 (created_at DESC)
-- deleted_at 필터와 함께 사용되므로 순서 고려
CREATE INDEX idx_post_created_deleted ON post(created_at, deleted_at);
