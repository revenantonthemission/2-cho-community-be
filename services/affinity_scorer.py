"""affinity_scorer: 추천 피드 점수 계산 순수 로직.

DB/HTTP 의존성 없음. 단위 테스트 가능.
"""

from dataclasses import dataclass, field

from models.affinity_models import UserSignals

# 신호 가중치 — 튜닝 시 이 상수만 수정
SIGNAL_WEIGHTS = {
    "liked_tag": 3.0,
    "bookmarked_tag": 3.0,
    "commented_tag": 1.5,
    "viewed_category": 1.0,
    "followed_author": 2.5,
    "liked_author": 0.8,
    "bookmarked_author": 0.8,
}

# 점수 구성 비율 (합계 = 1.0)
TAG_COEFF = 0.5
CATEGORY_COEFF = 0.3
AUTHOR_COEFF = 0.2


@dataclass
class UserAffinityProfile:
    """정규화된 사용자 친화도 프로필."""

    tag_weights: dict[int, float] = field(default_factory=dict)
    category_weights: dict[int, float] = field(default_factory=dict)
    author_weights: dict[int, float] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """프로필에 유효한 가중치가 있는지 확인합니다."""
        return not (self.tag_weights or self.category_weights or self.author_weights)


def _weighted_merge(*dicts_with_weight: tuple[dict[int, int], float]) -> dict[int, float]:
    """여러 카운트 딕셔너리를 가중합산합니다."""
    merged: dict[int, float] = {}
    for counts, weight in dicts_with_weight:
        for key, cnt in counts.items():
            merged[key] = merged.get(key, 0.0) + cnt * weight
    return merged


def _max_normalize(weights: dict[int, float]) -> dict[int, float]:
    """최대값 기준으로 0–1 범위로 정규화합니다."""
    if not weights:
        return {}
    max_val = max(weights.values())
    if max_val <= 0:
        return {}
    return {k: v / max_val for k, v in weights.items()}


def build_profile(signals: UserSignals) -> UserAffinityProfile:
    """UserSignals → 정규화된 UserAffinityProfile 변환.

    Args:
        signals: 사용자의 원시 상호작용 데이터.

    Returns:
        0–1 범위로 정규화된 친화도 프로필.
    """
    # 태그 가중합산
    raw_tags = _weighted_merge(
        (signals.liked_tag_counts, SIGNAL_WEIGHTS["liked_tag"]),
        (signals.bookmarked_tag_counts, SIGNAL_WEIGHTS["bookmarked_tag"]),
        (signals.commented_tag_counts, SIGNAL_WEIGHTS["commented_tag"]),
    )

    # 카테고리 가중합산
    raw_categories = _weighted_merge(
        (signals.viewed_category_counts, SIGNAL_WEIGHTS["viewed_category"]),
    )

    # 작성자 가중합산
    followed_as_counts = {aid: 1 for aid in signals.followed_author_ids}
    raw_authors = _weighted_merge(
        (followed_as_counts, SIGNAL_WEIGHTS["followed_author"]),
        (signals.liked_author_counts, SIGNAL_WEIGHTS["liked_author"]),
        (signals.bookmarked_author_counts, SIGNAL_WEIGHTS["bookmarked_author"]),
    )

    return UserAffinityProfile(
        tag_weights=_max_normalize(raw_tags),
        category_weights=_max_normalize(raw_categories),
        author_weights=_max_normalize(raw_authors),
    )


def score_post(
    profile: UserAffinityProfile,
    post_tag_ids: list[int],
    post_category_id: int | None,
    post_author_id: int | None,
) -> float:
    """단일 게시글에 대한 친화도 점수(0.0–1.0)를 계산합니다.

    Args:
        profile: 사용자 친화도 프로필.
        post_tag_ids: 게시글의 태그 ID 목록.
        post_category_id: 게시글 카테고리 ID.
        post_author_id: 게시글 작성자 ID.

    Returns:
        0.0–1.0 범위의 친화도 점수.
    """
    # 태그 점수: 겹치는 태그 가중치 평균
    tag_score = 0.0
    if post_tag_ids and profile.tag_weights:
        matched = sum(profile.tag_weights.get(tid, 0.0) for tid in post_tag_ids)
        tag_score = matched / len(post_tag_ids)

    # 카테고리 점수
    category_score = 0.0
    if post_category_id is not None:
        category_score = profile.category_weights.get(post_category_id, 0.0)

    # 작성자 점수
    author_score = 0.0
    if post_author_id is not None:
        author_score = profile.author_weights.get(post_author_id, 0.0)

    # 가중 결합 후 0–1 클리핑
    raw = tag_score * TAG_COEFF + category_score * CATEGORY_COEFF + author_score * AUTHOR_COEFF
    return max(0.0, min(1.0, raw))


def compute_combined_score(affinity: float, hot_score: float) -> float:
    """친화도와 hot_score를 결합합니다.

    Cold-start (affinity=0)이면 hot_score만 사용합니다.

    Args:
        affinity: 0.0–1.0 범위의 친화도 점수.
        hot_score: 게시글의 인기도 점수.

    Returns:
        결합 점수.
    """
    if affinity <= 0.0:
        return hot_score
    return affinity * hot_score
