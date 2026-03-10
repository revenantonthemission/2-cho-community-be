"""post_service: 게시글 관련 비즈니스 로직을 처리하는 서비스."""

import logging

from typing import List, Dict, Tuple, Optional
from models import post_models, tag_models, poll_models, follow_models, notification_models
from models.user_models import User
from models.like_models import get_like
from models.bookmark_models import get_bookmark
from models.block_models import get_blocked_user_ids
from schemas.post_schemas import CreatePostRequest
from utils.formatters import format_datetime
from utils.exceptions import not_found_error, forbidden_error, bad_request_error


class PostService:
    """게시글 관리 서비스."""

    @staticmethod
    async def get_posts(
        offset: int,
        limit: int,
        search: Optional[str] = None,
        sort: str = "latest",
        author_id: Optional[int] = None,
        category_id: Optional[int] = None,
        current_user: Optional[User] = None,
        tag: Optional[str] = None,
        following: bool = False,
    ) -> Tuple[List[Dict], int, bool]:
        """게시글 목록 조회 및 가공."""
        # 차단된 사용자 목록 조회
        blocked_ids: set[int] | None = None
        if current_user:
            blocked_ids = await get_blocked_user_ids(current_user.id)
            if not blocked_ids:
                blocked_ids = None

        # 팔로잉 피드 처리
        author_ids: set[int] | None = None
        if following and current_user:
            author_ids = await follow_models.get_following_ids(current_user.id)
            if not author_ids:
                return ([], 0, False)

        # 추천 피드 cold start 처리
        effective_sort = sort
        if sort == "for_you":
            if not current_user:
                effective_sort = "latest"
            else:
                from models.affinity_models import user_has_scores
                if not await user_has_scores(current_user.id):
                    effective_sort = "latest"

        # 추천 피드: 다양성 필터 여유분 확보
        fetch_limit = limit * 3 if effective_sort == "for_you" else limit

        # 1. DB 조회
        posts_data = await post_models.get_posts_with_details(
            offset, fetch_limit, search=search, sort=effective_sort,
            author_id=author_id, category_id=category_id,
            blocked_user_ids=blocked_ids, tag=tag,
            author_ids=author_ids,
            current_user_id=current_user.id if current_user and effective_sort == "for_you" else None,
        )
        total_count = await post_models.get_total_posts_count(
            search=search, author_id=author_id, category_id=category_id,
            blocked_user_ids=blocked_ids, tag=tag,
            author_ids=author_ids,
        )

        # 추천 피드 다양성 필터: 작성자당 최대 3개
        if effective_sort == "for_you":
            posts_data = PostService._apply_diversity_cap(posts_data, limit)

        has_more = offset + limit < total_count

        # 2. 데이터 가공 (날짜 포맷, 내용 요약)
        for post in posts_data:
            post["created_at"] = format_datetime(post["created_at"])
            post["updated_at"] = format_datetime(post.get("updated_at"))

            content = post["content"]
            if len(content) > 200:
                post["content"] = content[:200] + "..."

        # 태그 벌크 조회
        post_ids = [p["post_id"] for p in posts_data]
        posts_tags = await tag_models.get_posts_tags(post_ids)
        for post in posts_data:
            post["tags"] = posts_tags.get(post["post_id"], [])

        # 읽음 상태 조회 (로그인 사용자만)
        if current_user:
            read_ids = await post_models.get_read_post_ids(current_user.id, post_ids)
            for post in posts_data:
                post["is_read"] = post["post_id"] in read_ids
        else:
            for post in posts_data:
                post["is_read"] = False

        return posts_data, total_count, has_more

    @staticmethod
    def _apply_diversity_cap(
        posts: list[dict],
        limit: int,
        max_per_author: int = 3,
    ) -> list[dict]:
        """동일 작성자 게시글을 페이지당 최대 N개로 제한합니다."""
        author_count: dict[int | None, int] = {}
        result: list[dict] = []
        for post in posts:
            author_id = (post.get("author") or {}).get("user_id")
            count = author_count.get(author_id, 0)
            if author_id is not None and count >= max_per_author:
                continue
            if author_id is not None:
                author_count[author_id] = count + 1
            result.append(post)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    async def get_post_detail(
        post_id: int, current_user: Optional[User], timestamp: str,
        comment_sort: str = "oldest",
    ) -> Dict:
        """게시글 상세 조회 및 조회수 증가 처리."""
        # 1. 게시글 존재 확인
        post_data = await post_models.get_post_with_details(post_id)
        if not post_data:
            raise not_found_error("post", timestamp)

        # 2. 조회수 증가 (로그인 사용자, 하루 1회)
        if current_user:
            if await post_models.increment_view_count(post_id, current_user.id):
                post_data["views_count"] += 1

        # 3. 로그인 사용자 상태 플래그 + 차단 목록
        blocked_ids: set[int] | None = None
        if current_user:
            like = await get_like(post_id, current_user.id)
            post_data["is_liked"] = like is not None

            bookmark = await get_bookmark(post_id, current_user.id)
            post_data["is_bookmarked"] = bookmark is not None

            blocked_ids = await get_blocked_user_ids(current_user.id)

            # 게시글 작성자 차단 여부
            author_id = post_data.get("author", {}).get("user_id")
            post_data["is_blocked"] = (
                bool(blocked_ids) and author_id in blocked_ids
            )

            if not blocked_ids:
                blocked_ids = None
        else:
            post_data["is_liked"] = False
            post_data["is_bookmarked"] = False
            post_data["is_blocked"] = False

        # 4. 다중 이미지 조회 (post_image 우선, 없으면 image_url 폴백)
        images = await post_models.get_post_images(post_id)
        if images:
            post_data["image_urls"] = [img["image_url"] for img in images]
        elif post_data.get("image_url"):
            post_data["image_urls"] = [post_data["image_url"]]
        else:
            post_data["image_urls"] = []

        # 태그 목록 조회
        post_data["tags"] = await tag_models.get_post_tags(post_id)

        # 투표 데이터 조회
        post_data["poll"] = await poll_models.get_poll_by_post_id(
            post_id, current_user_id=current_user.id if current_user else None
        )

        # 5. 댓글 목록 조회
        comments_data = await post_models.get_comments_with_author(
            post_id,
            current_user_id=current_user.id if current_user else None,
            blocked_user_ids=blocked_ids,
            comment_sort=comment_sort,
        )

        # 6. 데이터 가공
        post_data["created_at"] = format_datetime(post_data["created_at"])
        post_data["updated_at"] = format_datetime(post_data.get("updated_at"))

        for comment in comments_data:
            comment["created_at"] = format_datetime(comment["created_at"])
            comment["updated_at"] = format_datetime(comment.get("updated_at"))
            for reply in comment.get("replies", []):
                reply["created_at"] = format_datetime(reply["created_at"])
                reply["updated_at"] = format_datetime(reply.get("updated_at"))

        return {"post": post_data, "comments": comments_data}

    @staticmethod
    async def create_post(
        user_id: int,
        post_data: CreatePostRequest,
        is_admin: bool = False,
        actor_nickname: str | None = None,
    ) -> int:
        """게시글 생성.

        공지사항 카테고리(id=4)는 관리자만 작성 가능합니다.
        """
        # 공지사항 카테고리는 관리자만 사용 가능
        if post_data.category_id == 4 and not is_admin:
            raise forbidden_error(
                "create", "", "공지사항은 관리자만 작성할 수 있습니다."
            )

        # image_urls 우선, 없으면 image_url 단일 필드 사용 (하위 호환)
        primary_image_url = post_data.image_url
        if post_data.image_urls:
            primary_image_url = post_data.image_urls[0]

        post = await post_models.create_post(
            author_id=user_id,
            title=post_data.title,
            content=post_data.content,
            image_url=primary_image_url,
            category_id=post_data.category_id,
        )

        # 다중 이미지 저장
        image_list = post_data.image_urls or (
            [post_data.image_url] if post_data.image_url else []
        )
        if image_list:
            await post_models.save_post_images(post.id, image_list)

        # 태그 저장
        if post_data.tags:
            tag_ids = await tag_models.get_or_create_tags(post_data.tags)
            await tag_models.save_post_tags(post.id, tag_ids)

        # 투표 생성
        if post_data.poll:
            await poll_models.create_poll(
                post_id=post.id,
                question=post_data.poll.question,
                options=post_data.poll.options,
                expires_at=post_data.poll.expires_at,
            )

        # 팔로워에게 새 게시글 알림 (실패해도 게시글 생성은 유지)
        try:
            follower_ids = await follow_models.get_follower_ids(user_id)
            for follower_id in follower_ids:
                await notification_models.create_notification(
                    user_id=follower_id,
                    notification_type="follow",
                    post_id=post.id,
                    actor_id=user_id,
                    actor_nickname=actor_nickname,
                )
        except Exception:
            logging.getLogger(__name__).warning(
                "팔로우 알림 생성 실패", exc_info=True
            )

        return post.id

    @staticmethod
    async def update_post(
        post_id: int,
        user_id: int,
        title: Optional[str],
        content: Optional[str],
        image_url: Optional[str],
        timestamp: str,
        category_id: Optional[int] = None,
        image_urls: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> Dict:
        """게시글 수정."""
        # 1. 존재 확인
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        # 2. 권한 확인
        if post.author_id != user_id:
            raise forbidden_error(
                "edit", timestamp, "게시글 작성자만 수정할 수 있습니다."
            )

        # 3. 변경사항 확인
        if all(v is None for v in (title, content, image_url, category_id, image_urls, tags)):
            raise bad_request_error("no_changes_provided", timestamp)

        # 4. 다중 이미지 처리
        effective_image_url = image_url
        if image_urls is not None and len(image_urls) > 0:
            effective_image_url = image_urls[0]
            await post_models.save_post_images(post_id, image_urls)

        # 태그 업데이트 (tags가 None이 아닌 경우에만 변경)
        if tags is not None:
            tag_ids = await tag_models.get_or_create_tags(tags)
            await tag_models.save_post_tags(post_id, tag_ids)

        # 5. DB 업데이트
        updated_post = await post_models.update_post(
            post_id,
            title=title,
            content=content,
            image_url=effective_image_url,
            category_id=category_id,
        )
        assert updated_post is not None  # 게시글 존재는 위에서 검증됨

        return {
            "post_id": updated_post.id,
            "title": updated_post.title,
            "content": updated_post.content,
            "updated_at": format_datetime(updated_post.updated_at),
        }

    @staticmethod
    async def delete_post(
        post_id: int,
        user_id: int,
        timestamp: str,
        is_admin: bool = False,
    ) -> None:
        """게시글 삭제. 관리자는 작성자 검증을 건너뜁니다."""
        # 1. 존재 확인
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        # 2. 권한 확인 (관리자는 모든 게시글 삭제 가능)
        if not is_admin and post.author_id != user_id:
            raise forbidden_error(
                "delete", timestamp, "게시글 작성자만 삭제할 수 있습니다."
            )

        # 3. DB 삭제
        await post_models.delete_post(post_id)

    @staticmethod
    async def get_related_posts(
        post_id: int,
        current_user: Optional[User] = None,
        limit: int = 5,
    ) -> Optional[List[Dict]]:
        """현재 게시글과 관련된 게시글 목록을 조회합니다.

        태그/카테고리 기반 관련도 정렬 후 반환합니다.

        Args:
            post_id: 기준 게시글 ID.
            current_user: 현재 로그인한 사용자 (차단 필터링용).
            limit: 최대 반환 개수.

        Returns:
            연관 게시글 목록, 기준 게시글이 없으면 None.
        """
        # 1. 게시글 존재 확인
        post = await post_models.get_post_by_id(post_id)
        if not post:
            return None

        # 2. 태그 조회 → tag_ids 추출
        tags = await tag_models.get_post_tags(post_id)
        tag_ids = [t["id"] for t in tags]

        # 3. 차단 사용자 조회 (로그인 시)
        blocked_ids: set[int] | None = None
        if current_user:
            blocked_ids = await get_blocked_user_ids(current_user.id)
            if not blocked_ids:
                blocked_ids = None

        # 4. 연관 게시글 조회
        posts_data = await post_models.get_related_posts(
            current_post_id=post_id,
            category_id=post.category_id,
            tag_ids=tag_ids,
            limit=limit,
            blocked_user_ids=blocked_ids,
        )

        # 5. 데이터 가공 (날짜 포맷, 내용 요약)
        for p in posts_data:
            p["created_at"] = format_datetime(p["created_at"])
            p["updated_at"] = format_datetime(p.get("updated_at"))
            content = p["content"]
            if len(content) > 200:
                p["content"] = content[:200] + "..."

        # 6. 태그 벌크 조회
        post_ids = [p["post_id"] for p in posts_data]
        posts_tags = await tag_models.get_posts_tags(post_ids)
        for p in posts_data:
            p["tags"] = posts_tags.get(p["post_id"], [])

        return posts_data

    @staticmethod
    async def pin_post(post_id: int, timestamp: str) -> None:
        """게시글 고정."""
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)
        await post_models.pin_post(post_id)

    @staticmethod
    async def unpin_post(post_id: int, timestamp: str) -> None:
        """게시글 고정 해제."""
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)
        await post_models.unpin_post(post_id)
