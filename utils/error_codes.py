"""error_codes: 전체 API 에러 코드를 중앙 관리하는 StrEnum 모듈."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    # 공통
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    UNAUTHORIZED = "unauthorized"
    BAD_REQUEST = "bad_request"
    NO_CHANGES_PROVIDED = "no_changes_provided"

    # 인증
    INVALID_CREDENTIALS = "invalid_credentials"
    SESSION_EXPIRED = "session_expired"
    ACCOUNT_SUSPENDED = "account_suspended"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    INVALID_REFRESH_TOKEN = "invalid_refresh_token"
    INVALID_OR_EXPIRED_TOKEN = "invalid_or_expired_token"
    ALREADY_VERIFIED = "already_verified"
    INVALID_PASSWORD = "invalid_password"
    PASSWORD_MISMATCH = "password_mismatch"
    SAME_PASSWORD = "same_password"
    INACTIVE_USER = "inactive_user"

    # 게시글
    POST_NOT_FOUND = "post_not_found"
    ALREADY_LIKED = "already_liked"
    LIKE_NOT_FOUND = "like_not_found"
    ALREADY_BOOKMARKED = "already_bookmarked"
    BOOKMARK_NOT_FOUND = "bookmark_not_found"

    # 댓글
    COMMENT_NOT_FOUND = "comment_not_found"
    COMMENT_NOT_IN_POST = "comment_not_in_post"
    PARENT_COMMENT_NOT_FOUND = "parent_comment_not_found"
    PARENT_COMMENT_NOT_IN_POST = "parent_comment_not_in_post"
    NESTED_REPLY_NOT_ALLOWED = "nested_reply_not_allowed"
    ALREADY_COMMENT_LIKED = "already_comment_liked"
    COMMENT_LIKE_NOT_FOUND = "comment_like_not_found"

    # 사용자
    USER_NOT_FOUND = "user_not_found"
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    NICKNAME_ALREADY_EXISTS = "nickname_already_exists"
    ALREADY_FOLLOWING = "already_following"
    FOLLOW_NOT_FOUND = "follow_not_found"
    ALREADY_BLOCKED = "already_blocked"
    BLOCK_NOT_FOUND = "block_not_found"
    SELF_ACTION_NOT_ALLOWED = "self_action_not_allowed"
    CANNOT_BLOCK_SELF = "cannot_block_self"
    CANNOT_FOLLOW_SELF = "cannot_follow_self"

    # 신고
    ALREADY_REPORTED = "already_reported"
    REPORT_ALREADY_EXISTS = "report_already_exists"
    REPORT_NOT_FOUND = "report_not_found"
    CANNOT_REPORT_OWN_CONTENT = "cannot_report_own_content"
    ALREADY_PROCESSED = "already_processed"

    # DM
    DM_BLOCKED = "dm_blocked"
    CONVERSATION_NOT_FOUND = "conversation_not_found"
    MESSAGE_NOT_FOUND = "message_not_found"
    SELF_CONVERSATION = "self_conversation"
    RECIPIENT_NOT_FOUND = "recipient_not_found"
    ALREADY_DELETED = "already_deleted"

    # 투표
    ALREADY_VOTED = "already_voted"
    POLL_EXPIRED = "poll_expired"
    POLL_NOT_FOUND = "poll_not_found"
    INVALID_OPTION = "invalid_option"

    # 관리자
    CANNOT_SUSPEND_SELF = "cannot_suspend_self"
    CANNOT_SUSPEND_ADMIN = "cannot_suspend_admin"
    USER_NOT_SUSPENDED = "user_not_suspended"

    # 알림
    NOTIFICATION_NOT_FOUND = "notification_not_found"
