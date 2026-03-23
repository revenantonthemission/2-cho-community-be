"""models: 데이터 클래스 및 데이터 관리 함수 패키지.

사용자, 게시글, 댓글, 좋아요 관련 데이터 모델과 MySQL 데이터베이스 관리 함수를 제공합니다.
"""

from .activity_models import (
    get_my_comments,
    get_my_likes,
    get_my_posts,
)
from .category_models import (
    Category,
    get_all_categories,
    get_category_by_id,
)
from .comment_models import (
    Comment,
    create_comment,
    delete_comment,
    get_comment_by_id,
    get_comments_by_post,
    get_comments_count_by_post,
    update_comment,
)
from .like_models import (
    Like,
    add_like,
    get_like,
    get_post_likes_count,
    remove_like,
)
from .notification_models import (
    create_notification,
    delete_notification,
    get_notifications,
    get_unread_count,
    mark_all_as_read,
    mark_as_read,
)
from .post_models import (
    Post,
    create_post,
    delete_post,
    get_comments_with_author,
    get_post_by_id,
    get_post_with_details,
    get_posts_with_details,
    get_total_posts_count,
    increment_view_count,
    update_post,
)
from .report_models import (
    Report,
    create_report,
    get_report_by_id,
    get_reports,
    get_reports_count,
    resolve_report,
)
from .token_models import (
    atomic_rotate_refresh_token,
    cleanup_expired_tokens,
    create_refresh_token,
    delete_refresh_token,
    get_refresh_token,
)
from .user_models import (
    User,
    add_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_nickname,
    update_password,
    update_user,
    withdraw_user,
)
from .verification_models import (
    cleanup_expired_verification_tokens,
    create_verification_token,
    is_user_verified,
    verify_token,
)

__all__ = [
    # 카테고리 모델
    "Category",
    "Comment",
    "Like",
    # 게시글 모델
    "Post",
    # 신고 모델
    "Report",
    # 사용자 모델
    "User",
    "add_like",
    "add_user",
    "atomic_rotate_refresh_token",
    "cleanup_expired_tokens",
    "cleanup_expired_verification_tokens",
    "create_comment",
    # 알림 모델
    "create_notification",
    "create_post",
    # 리프레시 토큰 모델
    "create_refresh_token",
    "create_report",
    # 이메일 인증 토큰 모델
    "create_verification_token",
    "delete_comment",
    "delete_notification",
    "delete_post",
    "delete_refresh_token",
    "get_all_categories",
    "get_category_by_id",
    "get_comment_by_id",
    "get_comments_by_post",
    "get_comments_count_by_post",
    "get_comments_with_author",
    "get_like",
    "get_my_comments",
    "get_my_likes",
    # 내 활동 모델
    "get_my_posts",
    "get_notifications",
    "get_post_by_id",
    "get_post_likes_count",
    "get_post_with_details",
    # 최적화된 함수 (N+1 문제 해결)
    "get_posts_with_details",
    "get_refresh_token",
    "get_report_by_id",
    "get_reports",
    "get_reports_count",
    "get_total_posts_count",
    "get_unread_count",
    "get_user_by_email",
    "get_user_by_id",
    "get_user_by_nickname",
    "increment_view_count",
    "is_user_verified",
    "mark_all_as_read",
    "mark_as_read",
    "remove_like",
    "resolve_report",
    "update_comment",
    "update_password",
    "update_post",
    "update_user",
    "verify_token",
    "withdraw_user",
]
