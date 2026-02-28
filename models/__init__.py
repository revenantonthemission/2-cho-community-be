"""models: 데이터 클래스 및 데이터 관리 함수 패키지.

사용자, 게시글, 댓글, 좋아요 관련 데이터 모델과 MySQL 데이터베이스 관리 함수를 제공합니다.
"""

from .user_models import (
    User,
    get_user_by_id,
    get_user_by_email,
    get_user_by_nickname,
    add_user,
    update_user,
    update_password,
    withdraw_user,
)

from .post_models import (
    Post,
    get_total_posts_count,
    get_post_by_id,
    create_post,
    update_post,
    delete_post,
    increment_view_count,
    get_posts_with_details,
    get_post_with_details,
    get_comments_with_author,
)

from .comment_models import (
    Comment,
    get_comments_by_post,
    get_comments_count_by_post,
    get_comment_by_id,
    create_comment,
    update_comment,
    delete_comment,
)

from .like_models import (
    Like,
    get_like,
    get_post_likes_count,
    add_like,
    remove_like,
)

from .token_models import (
    create_refresh_token,
    get_refresh_token,
    delete_refresh_token,
    rotate_refresh_token,
    cleanup_expired_tokens,
)

__all__ = [
    # 사용자 모델
    "User",
    "get_user_by_id",
    "get_user_by_email",
    "get_user_by_nickname",
    "add_user",
    "update_user",
    "update_password",
    "withdraw_user",
    # 게시글 모델
    "Post",
    "Comment",
    "Like",
    "get_total_posts_count",
    "get_post_by_id",
    "create_post",
    "update_post",
    "delete_post",
    "increment_view_count",
    "get_like",
    "get_post_likes_count",
    "add_like",
    "remove_like",
    "get_comments_by_post",
    "get_comments_count_by_post",
    "get_comment_by_id",
    "create_comment",
    "update_comment",
    "delete_comment",
    # 최적화된 함수 (N+1 문제 해결)
    "get_posts_with_details",
    "get_post_with_details",
    "get_comments_with_author",
    # 리프레시 토큰 모델
    "create_refresh_token",
    "get_refresh_token",
    "delete_refresh_token",
    "rotate_refresh_token",
    "cleanup_expired_tokens",
]
