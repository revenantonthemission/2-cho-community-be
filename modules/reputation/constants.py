"""평판 시스템 상수 정의."""

# 이벤트별 포인트 값
POINTS = {
    "post_liked": 10,
    "post_like_given": 1,
    "comment_liked": 5,
    "comment_like_given": 1,
    "answer_accepted": 50,
    "post_created": 5,
    "comment_created": 2,
    "wiki_created": 20,
    "wiki_edited": 10,
    "package_review_created": 15,
    "dm_sent": 0,
}

# 이벤트 → 배지 trigger_type 매핑
EVENT_TO_BADGE_TRIGGERS: dict[str, list[str]] = {
    "post_created": ["post_count"],
    "comment_created": ["comment_count"],
    "post_liked": ["single_post_likes"],
    "comment_liked": ["single_comment_likes"],
    "post_like_given": ["like_given_count"],
    "comment_like_given": ["like_given_count"],
    "answer_accepted": ["accepted_answer_count"],
    "wiki_created": ["wiki_edit_count"],
    "wiki_edited": ["wiki_edit_count"],
    "package_review_created": ["package_review_count"],
    "bookmark_created": ["bookmark_count"],
    "dm_sent": ["dm_sent_count"],
    "post_viewed": ["post_view_count", "single_post_views"],
    "follower_gained": ["follower_count"],
    "profile_updated": ["profile_completed"],
    "reputation_changed": ["reputation_score"],
    "badge_earned": ["badge_count"],
    "daily_visit": ["consecutive_visit_days"],
}
