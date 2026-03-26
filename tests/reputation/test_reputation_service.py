"""Reputation 도메인 — 서비스 레이어 테스트."""

import pytest
from httpx import AsyncClient

from modules.reputation import models as rep_models
from modules.reputation.service import ReputationService
from tests.conftest import create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# award_points 기본 동작
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_award_points_updates_score(client: AsyncClient, fake):
    """award_points 호출 시 사용자 평판 점수가 올바르게 증가해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    await ReputationService.award_points(
        user_id=user_id,
        event_type="post_created",
        points=5,
        source_type="post",
        source_id=1,
    )

    # Assert
    score = await rep_models.get_user_reputation_score(user_id)
    assert score == 5


@pytest.mark.asyncio
async def test_award_points_zero_does_not_change_score(client: AsyncClient, fake):
    """points=0인 이벤트는 점수를 변경하지 않아야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    await ReputationService.award_points(
        user_id=user_id,
        event_type="dm_sent",
        points=0,
        source_type="dm",
        source_id=1,
    )

    # Assert
    score = await rep_models.get_user_reputation_score(user_id)
    assert score == 0


# ---------------------------------------------------------------------------
# award_points + 배지 트리거
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_award_points_triggers_first_post_badge(client: AsyncClient, fake):
    """게시글 생성 후 award_points 호출 시 'First Post' 배지가 수여되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # 실제 게시글 생성 (count_user_posts가 1을 반환하도록)
    await create_test_post(client, user["headers"])

    # Act
    await ReputationService.award_points(
        user_id=user_id,
        event_type="post_created",
        points=5,
        source_type="post",
        source_id=1,
    )

    # Assert
    badges = await rep_models.get_user_badges(user_id)
    badge_names = [b["name"] for b in badges]
    assert "First Post" in badge_names


@pytest.mark.asyncio
async def test_award_points_badge_adds_bonus_points(client: AsyncClient, fake):
    """배지 수여 시 배지의 points_awarded만큼 추가 점수가 반영되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act — API를 통해 게시글 생성 → post_created 이벤트 (5점) + First Post 배지 보너스 (5점)
    await create_test_post(client, user["headers"])

    # Assert — post_created 5점 + First Post 배지 보너스 5점 = 10점
    score = await rep_models.get_user_reputation_score(user_id)
    assert score == 10


# ---------------------------------------------------------------------------
# revoke_points
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_points_decreases_score(client: AsyncClient, fake):
    """revoke_points 호출 시 원래 포인트만큼 점수가 감소해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    await ReputationService.award_points(
        user_id=user_id,
        event_type="post_liked",
        points=10,
        source_type="post",
        source_id=42,
    )
    score_before = await rep_models.get_user_reputation_score(user_id)

    # Act
    await ReputationService.revoke_points(
        user_id=user_id,
        event_type="post_liked",
        source_type="post",
        source_id=42,
    )

    # Assert
    score_after = await rep_models.get_user_reputation_score(user_id)
    assert score_after == score_before - 10


@pytest.mark.asyncio
async def test_revoke_points_no_original_event_is_noop(client: AsyncClient, fake):
    """원본 이벤트가 없을 때 revoke_points는 아무 작업도 하지 않아야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act — 원본 이벤트가 없는 상태에서 회수 시도
    await ReputationService.revoke_points(
        user_id=user_id,
        event_type="post_liked",
        source_type="post",
        source_id=999,
    )

    # Assert — 크래시 없이 점수 변화 없음
    score = await rep_models.get_user_reputation_score(user_id)
    assert score == 0


# ---------------------------------------------------------------------------
# 신뢰 등급 승급
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trust_level_upgrades_on_threshold(client: AsyncClient, fake):
    """점수가 50 이상이면 신뢰 등급이 1(Member)로 승급되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act — 50점 부여
    await ReputationService.award_points(
        user_id=user_id,
        event_type="answer_accepted",
        points=50,
        source_type="comment",
        source_id=1,
    )

    # Assert
    level = await rep_models.get_user_trust_level(user_id)
    assert level >= 1


@pytest.mark.asyncio
async def test_trust_level_stays_when_below_threshold(client: AsyncClient, fake):
    """점수가 50 미만이면 신뢰 등급은 0(New User)을 유지해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act — 49점 미만 (5 + 배지 보너스는 별도이지만 총합이 50 미만)
    await ReputationService.award_points(
        user_id=user_id,
        event_type="comment_created",
        points=2,
        source_type="comment",
        source_id=1,
    )

    # Assert
    level = await rep_models.get_user_trust_level(user_id)
    assert level == 0


# ---------------------------------------------------------------------------
# record_daily_visit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_daily_visit_no_crash_on_duplicate(client: AsyncClient, fake):
    """같은 날 중복 방문 기록 시 에러 없이 처리되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act — 두 번 호출
    await ReputationService.record_daily_visit(user_id)
    await ReputationService.record_daily_visit(user_id)

    # Assert — 크래시 없으면 성공
    streak = await rep_models.get_consecutive_visit_days(user_id)
    assert streak == 1


@pytest.mark.asyncio
async def test_record_daily_visit_records_event(client: AsyncClient, fake):
    """첫 방문 기록 시 배지 체크가 실행되어야 한다 (연속 방문일 = 1)."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    await ReputationService.record_daily_visit(user_id)

    # Assert — 연속 방문 1일이므로 14일 배지는 미수여
    badges = await rep_models.get_user_badges(user_id)
    badge_names = [b["name"] for b in badges]
    assert "Devoted" not in badge_names


# ---------------------------------------------------------------------------
# 이벤트 히스토리 기록 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_award_points_creates_event_record(client: AsyncClient, fake):
    """award_points 호출 시 reputation_event 테이블에 이벤트가 기록되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    await ReputationService.award_points(
        user_id=user_id,
        event_type="wiki_created",
        points=20,
        source_type="wiki",
        source_id=1,
    )

    # Assert
    history = await rep_models.get_reputation_history(user_id)
    event_types = [e["event_type"] for e in history]
    assert "wiki_created" in event_types
