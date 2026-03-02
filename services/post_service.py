"""post_service: 게시글 관련 비즈니스 로직을 처리하는 서비스."""

from typing import List, Dict, Tuple, Optional
from models import post_models
from models.user_models import User
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
    ) -> Tuple[List[Dict], int, bool]:
        """게시글 목록 조회 및 가공."""
        # 1. DB 조회
        posts_data = await post_models.get_posts_with_details(
            offset, limit, search=search, sort=sort,
            author_id=author_id, category_id=category_id,
        )
        total_count = await post_models.get_total_posts_count(
            search=search, author_id=author_id, category_id=category_id,
        )
        has_more = offset + limit < total_count

        # 2. 데이터 가공 (날짜 포맷, 내용 요약)
        for post in posts_data:
            post["created_at"] = format_datetime(post["created_at"])
            post["updated_at"] = format_datetime(post.get("updated_at"))

            content = post["content"]
            if len(content) > 200:
                post["content"] = content[:200] + "..."

        return posts_data, total_count, has_more

    @staticmethod
    async def get_post_detail(
        post_id: int, current_user: Optional[User], timestamp: str
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

        # 3. 댓글 목록 조회
        comments_data = await post_models.get_comments_with_author(post_id)

        # 4. 데이터 가공
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
    ) -> int:
        """게시글 생성.

        공지사항 카테고리(id=4)는 관리자만 작성 가능합니다.
        """
        # 공지사항 카테고리는 관리자만 사용 가능
        if post_data.category_id == 4 and not is_admin:
            raise forbidden_error(
                "create", "", "공지사항은 관리자만 작성할 수 있습니다."
            )

        post = await post_models.create_post(
            author_id=user_id,
            title=post_data.title,
            content=post_data.content,
            image_url=post_data.image_url,
            category_id=post_data.category_id,
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
        if all(v is None for v in (title, content, image_url, category_id)):
            raise bad_request_error("no_changes_provided", timestamp)

        # 4. DB 업데이트
        updated_post = await post_models.update_post(
            post_id,
            title=title,
            content=content,
            image_url=image_url,
            category_id=category_id,
        )
        assert updated_post is not None  # 게시글 존재는 위에서 검증됨

        return {
            "post_id": updated_post.id,
            "title": updated_post.title,
            "content": updated_post.content,
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
