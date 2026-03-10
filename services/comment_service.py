"""comment_service: 댓글 관련 비즈니스 로직을 처리하는 서비스."""

import logging

from models import post_models, comment_models
from models.user_models import get_user_by_nickname
from utils.exceptions import not_found_error, bad_request_error, forbidden_error, safe_notify
from utils.mention import extract_mentions

logger = logging.getLogger(__name__)


class CommentService:
    """댓글 관리 서비스."""

    @staticmethod
    async def _validate_access(
        post_id: int,
        comment_id: int,
        timestamp: str,
    ) -> tuple:
        """게시글/댓글 존재 및 소속 검증.

        Args:
            post_id: 게시글 ID.
            comment_id: 댓글 ID.
            timestamp: 요청 타임스탬프.

        Returns:
            (post, comment) 튜플.

        Raises:
            HTTPException: 게시글/댓글 없으면 404, 소속 불일치면 400.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        comment = await comment_models.get_comment_by_id(comment_id)
        if not comment:
            raise not_found_error("comment", timestamp)

        if comment.post_id != post_id:
            raise bad_request_error(
                "comment_not_in_post", timestamp,
            )

        return post, comment

    @staticmethod
    async def create_comment(
        post_id: int,
        user_id: int,
        content: str,
        parent_id: int | None,
        actor_nickname: str,
        timestamp: str,
    ) -> comment_models.Comment:
        """댓글 생성 (대댓글 1단계 제한 포함).

        Args:
            post_id: 댓글을 작성할 게시글 ID.
            user_id: 작성자 ID.
            content: 댓글 내용.
            parent_id: 부모 댓글 ID (대댓글인 경우).
            actor_nickname: 알림에 표시할 사용자 닉네임.
            timestamp: 요청 타임스탬프.

        Returns:
            생성된 댓글 객체.

        Raises:
            HTTPException: 게시글 없으면 404, 대댓글 검증 실패 시 400.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        # 대댓글 검증
        parent_comment = None
        if parent_id is not None:
            parent_comment = await comment_models.get_comment_by_id(parent_id)

            if not parent_comment:
                raise bad_request_error(
                    "parent_comment_not_found", timestamp,
                    message="삭제된 댓글에 답글을 달 수 없습니다.",
                )

            if parent_comment.post_id != post_id:
                raise bad_request_error(
                    "parent_comment_not_in_post", timestamp,
                    message="해당 게시글의 댓글이 아닙니다.",
                )

            # 1단계 제한: 부모가 이미 대댓글이면 거부
            if parent_comment.parent_id is not None:
                raise bad_request_error(
                    "nested_reply_not_allowed", timestamp,
                    message="1단계 대댓글만 가능합니다.",
                )

        comment = await comment_models.create_comment(
            post_id=post_id,
            author_id=user_id,
            content=content,
            parent_id=parent_id,
        )

        # 알림 생성 (실패해도 댓글 생성에 영향 없음)
        if comment.parent_id and parent_id is not None:
            # 대댓글 → 부모 댓글 작성자에게 알림
            if parent_comment and parent_comment.author_id:
                await safe_notify(
                    user_id=parent_comment.author_id,
                    notification_type="comment",
                    actor_id=user_id,
                    actor_nickname=actor_nickname,
                    post_id=post_id,
                    comment_id=comment.id,
                )
        else:
            # 일반 댓글 → 게시글 작성자에게 알림
            if post.author_id:
                await safe_notify(
                    user_id=post.author_id,
                    notification_type="comment",
                    actor_id=user_id,
                    actor_nickname=actor_nickname,
                    post_id=post_id,
                    comment_id=comment.id,
                )

        # 멘션 알림 — 이미 comment 알림을 받은 사용자는 제외
        already_notified = {user_id}  # 자기 자신 제외
        if comment.parent_id and parent_id is not None:
            if parent_comment and parent_comment.author_id:
                already_notified.add(parent_comment.author_id)
        else:
            if post.author_id:
                already_notified.add(post.author_id)

        nicknames = extract_mentions(content)
        for nickname in nicknames:
            try:
                mentioned_user = await get_user_by_nickname(nickname)
            except Exception:
                logger.warning("멘션 사용자 조회 실패: %s", nickname, exc_info=True)
                continue
            if mentioned_user and mentioned_user.id not in already_notified:
                already_notified.add(mentioned_user.id)
                await safe_notify(
                    user_id=mentioned_user.id,
                    notification_type="mention",
                    actor_id=user_id,
                    actor_nickname=actor_nickname,
                    post_id=post_id,
                    comment_id=comment.id,
                )

        return comment

    @staticmethod
    async def update_comment(
        post_id: int,
        comment_id: int,
        user_id: int,
        content: str,
        timestamp: str,
    ) -> comment_models.Comment:
        """댓글 수정.

        Args:
            post_id: 게시글 ID.
            comment_id: 수정할 댓글 ID.
            user_id: 요청 사용자 ID.
            content: 수정할 내용.
            timestamp: 요청 타임스탬프.

        Returns:
            수정된 댓글 객체.

        Raises:
            HTTPException: 게시글/댓글 없으면 404, 권한 없으면 403.
        """
        _, comment = await CommentService._validate_access(
            post_id, comment_id, timestamp,
        )

        if comment.author_id != user_id:
            raise forbidden_error(
                "edit", timestamp,
                message="댓글 작성자만 수정/삭제할 수 있습니다.",
            )

        updated_comment = await comment_models.update_comment(
            comment_id, content,
        )
        assert updated_comment is not None  # 댓글 존재는 위에서 검증됨

        return updated_comment

    @staticmethod
    async def delete_comment(
        post_id: int,
        comment_id: int,
        user_id: int,
        timestamp: str,
        is_admin: bool = False,
    ) -> None:
        """댓글 삭제 (soft delete).

        Args:
            post_id: 게시글 ID.
            comment_id: 삭제할 댓글 ID.
            user_id: 요청 사용자 ID.
            timestamp: 요청 타임스탬프.
            is_admin: 관리자 여부 (True면 작성자 검증 스킵).

        Raises:
            HTTPException: 게시글/댓글 없으면 404, 권한 없으면 403.
        """
        _, comment = await CommentService._validate_access(
            post_id, comment_id, timestamp,
        )

        # 관리자가 아닌 경우 작성자 검증
        if not is_admin and comment.author_id != user_id:
            raise forbidden_error(
                "delete", timestamp,
                message="댓글 작성자만 수정/삭제할 수 있습니다.",
            )

        await comment_models.delete_comment(comment_id)
