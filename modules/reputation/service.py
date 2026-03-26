"""평판 시스템 비즈니스 로직."""

import logging
from collections.abc import Callable, Coroutine

from modules.reputation import models as rep_models
from modules.reputation.constants import EVENT_TO_BADGE_TRIGGERS

logger = logging.getLogger(__name__)

# trigger_type → 집계 함수 매핑 (source_id 불필요한 것들)
_TRIGGER_COUNT_FUNCS: dict[str, Callable[..., Coroutine]] = {
    "post_count": rep_models.count_user_posts,
    "comment_count": rep_models.count_user_comments,
    "like_given_count": rep_models.count_user_likes_given,
    "bookmark_count": rep_models.count_user_bookmarks,
    "accepted_answer_count": rep_models.count_user_accepted_answers,
    "wiki_edit_count": rep_models.count_user_wiki_edits,
    "package_review_count": rep_models.count_user_package_reviews,
    "dm_sent_count": rep_models.count_user_dm_sent,
    "follower_count": rep_models.count_user_followers,
    "post_view_count": rep_models.count_user_post_views,
    "badge_count": rep_models.get_user_badge_count,
    "reputation_score": rep_models.get_user_reputation_score,
}


class ReputationService:
    """평판 포인트 부여/회수, 배지 체크, 신뢰 등급 관리 서비스."""

    @staticmethod
    async def award_points(
        user_id: int,
        event_type: str,
        points: int,
        source_user_id: int | None = None,
        source_type: str | None = None,
        source_id: int | None = None,
    ) -> None:
        """평판 이벤트를 기록하고 점수를 갱신한 뒤 배지/신뢰 등급을 체크한다."""
        await rep_models.insert_reputation_event(
            user_id=user_id,
            event_type=event_type,
            points=points,
            source_user_id=source_user_id,
            source_type=source_type,
            source_id=source_id,
        )

        if points != 0:
            await rep_models.update_user_reputation(user_id, delta=points)

        await ReputationService._check_trust_level(user_id)
        await ReputationService._check_badges(user_id, event_type, source_type, source_id)

    @staticmethod
    async def revoke_points(
        user_id: int,
        event_type: str,
        source_type: str,
        source_id: int,
    ) -> None:
        """기존 이벤트를 찾아 포인트를 회수(음수 이벤트 삽입)한다."""
        original = await rep_models.find_original_event(user_id, event_type, source_type, source_id)
        if not original:
            logger.warning(
                "회수할 원본 이벤트 없음: user_id=%s, event_type=%s, source=%s/%s",
                user_id,
                event_type,
                source_type,
                source_id,
            )
            return

        negative_points = -original["points"]

        await rep_models.insert_reputation_event(
            user_id=user_id,
            event_type=event_type,
            points=negative_points,
            source_user_id=original.get("source_user_id"),
            source_type=source_type,
            source_id=source_id,
        )

        await rep_models.update_user_reputation(user_id, delta=negative_points)
        await ReputationService._check_trust_level(user_id)

    @staticmethod
    async def record_daily_visit(user_id: int) -> None:
        """일일 방문을 기록하고, 신규 방문인 경우 배지를 체크한다."""
        is_new = await rep_models.record_daily_visit(user_id)
        if is_new:
            await ReputationService._check_badges(user_id, "daily_visit", None, None)

    @staticmethod
    async def _check_trust_level(user_id: int) -> None:
        """현재 점수에 맞는 신뢰 등급으로 승급시키고 알림을 전송한다."""
        score = await rep_models.get_user_reputation_score(user_id)
        current_level = await rep_models.get_user_trust_level(user_id)
        appropriate_level = await rep_models.get_appropriate_trust_level(score)

        # 승급만 허용 (강등은 하지 않음)
        if appropriate_level > current_level:
            changed = await rep_models.update_user_trust_level(user_id, appropriate_level)
            if changed:
                logger.info(
                    "신뢰 등급 승급: user_id=%s, %s → %s",
                    user_id,
                    current_level,
                    appropriate_level,
                )
                # safe_notify에 "level_up" 타입이 아직 없으므로 try/except 처리 (Task 5에서 추가 예정)
                try:
                    from core.utils.exceptions import safe_notify

                    await safe_notify(
                        user_id=user_id,
                        notification_type="level_up",  # type: ignore[arg-type]
                        actor_id=user_id,
                        actor_nickname="",
                    )
                except Exception:
                    logger.debug("신뢰 등급 알림 전송 실패 (아직 미지원 타입)", exc_info=True)

    @staticmethod
    async def _check_badges(
        user_id: int,
        event_type: str,
        source_type: str | None,
        source_id: int | None,
    ) -> None:
        """이벤트에 연관된 배지 트리거를 확인하고 조건 충족 시 배지를 수여한다."""
        trigger_types = EVENT_TO_BADGE_TRIGGERS.get(event_type, [])
        if not trigger_types:
            return

        for trigger_type in trigger_types:
            badge_defs = await rep_models.get_badge_definitions_by_trigger(trigger_type)
            if not badge_defs:
                continue

            current_value = await ReputationService._get_trigger_value(user_id, trigger_type, source_type, source_id)

            for badge_def in badge_defs:
                if current_value >= badge_def["trigger_threshold"]:
                    awarded = await rep_models.award_badge(user_id, badge_def["id"])
                    if awarded:
                        logger.info(
                            "배지 수여: user_id=%s, badge='%s'",
                            user_id,
                            badge_def["name"],
                        )

                        # 배지에 추가 포인트가 있으면 점수 반영
                        if badge_def["points_awarded"] > 0:
                            await rep_models.insert_reputation_event(
                                user_id=user_id,
                                event_type="badge_earned",
                                points=badge_def["points_awarded"],
                                source_type="badge",
                                source_id=badge_def["id"],
                            )
                            await rep_models.update_user_reputation(user_id, delta=badge_def["points_awarded"])
                            await ReputationService._check_trust_level(user_id)

                        # Completionist 배지 체크 (badge_count 트리거의 재귀 방지)
                        if trigger_type != "badge_count":
                            completionist_defs = await rep_models.get_badge_definitions_by_trigger("badge_count")
                            badge_count = await rep_models.get_user_badge_count(user_id)
                            for comp_def in completionist_defs:
                                if badge_count >= comp_def["trigger_threshold"]:
                                    comp_awarded = await rep_models.award_badge(user_id, comp_def["id"])
                                    if comp_awarded:
                                        logger.info(
                                            "Completionist 배지 수여: user_id=%s",
                                            user_id,
                                        )
                                        if comp_def["points_awarded"] > 0:
                                            await rep_models.insert_reputation_event(
                                                user_id=user_id,
                                                event_type="badge_earned",
                                                points=comp_def["points_awarded"],
                                                source_type="badge",
                                                source_id=comp_def["id"],
                                            )
                                            await rep_models.update_user_reputation(
                                                user_id,
                                                delta=comp_def["points_awarded"],
                                            )
                                            await ReputationService._check_trust_level(user_id)

                        # 배지 획득 알림 (아직 미지원 타입이므로 try/except)
                        try:
                            from core.utils.exceptions import safe_notify

                            await safe_notify(
                                user_id=user_id,
                                notification_type="badge_earned",  # type: ignore[arg-type]
                                actor_id=user_id,
                                actor_nickname="",
                            )
                        except Exception:
                            logger.debug(
                                "배지 획득 알림 전송 실패 (아직 미지원 타입)",
                                exc_info=True,
                            )

    @staticmethod
    async def _get_trigger_value(
        user_id: int,
        trigger_type: str,
        source_type: str | None,
        source_id: int | None,
    ) -> int:
        """trigger_type에 해당하는 현재 값을 조회한다."""
        # 개별 게시글/댓글 기반 트리거 — source_id 필요
        if trigger_type == "single_post_likes" and source_id is not None:
            return await rep_models.count_single_post_likes(source_id)

        if trigger_type == "single_post_views" and source_id is not None:
            return await rep_models.get_post_views(source_id)

        if trigger_type == "single_comment_likes" and source_id is not None:
            return await rep_models.count_single_comment_likes(source_id)

        # 프로필 완성 여부 (bool → 0/1)
        if trigger_type == "profile_completed":
            completed = await rep_models.is_profile_completed(user_id)
            return 1 if completed else 0

        # 연속 방문일
        if trigger_type == "consecutive_visit_days":
            return await rep_models.get_consecutive_visit_days(user_id)

        # per-object 트리거에 source_id가 없으면 경고
        if trigger_type in ("single_post_likes", "single_post_views", "single_comment_likes"):
            logger.warning(
                "per-object trigger '%s' 호출 시 source_id 누락 (user_id=%s)",
                trigger_type,
                user_id,
            )
            return 0

        # 나머지 — user_id 기반 집계 함수
        func = _TRIGGER_COUNT_FUNCS.get(trigger_type)
        if func is not None:
            return await func(user_id)

        logger.warning("알 수 없는 trigger_type: %s", trigger_type)
        return 0
