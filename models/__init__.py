"""models: 데이터 클래스 및 데이터 관리 함수 패키지.

사용자, 게시글, 댓글, 좋아요 관련 데이터 모델과 MySQL 데이터베이스 관리 함수를 제공합니다.
"""

from .user_models import (
    User,
    get_users,
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
    clear_all_data,
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

from .session_models import (
    create_session,
    get_session,
    delete_session,
    delete_user_sessions,
)

__all__ = [
    # User models
    "User",
    "get_users",
    "get_user_by_id",
    "get_user_by_email",
    "get_user_by_nickname",
    "add_user",
    "update_user",
    "update_password",
    "withdraw_user",
    # Post models
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
    "clear_all_data",
    # Optimized (N+1 fix)
    "get_posts_with_details",
    "get_post_with_details",
    "get_comments_with_author",
    # Session models
    "create_session",
    "get_session",
    "delete_session",
    "delete_user_sessions",
]
