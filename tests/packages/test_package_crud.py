"""Package 도메인 — CRUD 및 리뷰 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_admin_user, create_verified_user

# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

PACKAGE_BASE_URL = "/v1/packages/"


def _make_package_payload(**overrides) -> dict:
    """패키지 생성용 페이로드를 생성한다."""
    payload = {
        "name": "neovim",
        "display_name": "Neovim",
        "description": "Vim 기반의 하이퍼 확장 가능한 텍스트 에디터",
        "homepage_url": "https://neovim.io",
        "category": "editor",
        "package_manager": "apt",
    }
    payload.update(overrides)
    return payload


def _make_review_payload(**overrides) -> dict:
    """리뷰 생성용 페이로드를 생성한다."""
    payload = {
        "rating": 5,
        "title": "최고의 에디터",
        "content": "Neovim은 정말 최고의 텍스트 에디터입니다. 강력 추천합니다.",
    }
    payload.update(overrides)
    return payload


async def _create_package(client: AsyncClient, headers: dict, **overrides) -> int:
    """패키지를 생성하고 package_id를 반환한다."""
    payload = _make_package_payload(**overrides)
    res = await client.post(PACKAGE_BASE_URL, json=payload, headers=headers)
    assert res.status_code == 201, f"패키지 생성 실패: {res.status_code}, {res.text}"
    return res.json()["data"]["package_id"]


async def _create_review(client: AsyncClient, headers: dict, package_id: int, **overrides) -> int:
    """리뷰를 생성하고 review_id를 반환한다."""
    payload = _make_review_payload(**overrides)
    res = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201, f"리뷰 생성 실패: {res.status_code}, {res.text}"
    return res.json()["data"]["review_id"]


# ===========================================================================
# 패키지 생성
# ===========================================================================


@pytest.mark.asyncio
async def test_create_package_returns_201(client: AsyncClient, fake):
    """유효한 데이터로 패키지 생성 시 201을 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        PACKAGE_BASE_URL,
        json=_make_package_payload(),
        headers=user["headers"],
    )

    assert res.status_code == 201
    data = res.json()["data"]
    assert "package_id" in data
    assert data["package_id"] > 0


@pytest.mark.asyncio
async def test_create_package_duplicate_name_returns_400(client: AsyncClient, fake):
    """동일한 이름의 패키지를 중복 등록하면 400 PACKAGE_NAME_DUPLICATE를 반환한다."""
    user = await create_verified_user(client, fake)
    payload = _make_package_payload()

    # 첫 번째 생성 — 성공
    res1 = await client.post(PACKAGE_BASE_URL, json=payload, headers=user["headers"])
    assert res1.status_code == 201

    # 두 번째 생성 — 중복
    res2 = await client.post(PACKAGE_BASE_URL, json=payload, headers=user["headers"])
    assert res2.status_code == 400
    assert res2.json()["detail"]["error"] == "PACKAGE_NAME_DUPLICATE"


@pytest.mark.asyncio
async def test_create_package_invalid_category_returns_422(client: AsyncClient, fake):
    """유효하지 않은 카테고리로 패키지 생성 시 422를 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        PACKAGE_BASE_URL,
        json=_make_package_payload(category="invalid_category"),
        headers=user["headers"],
    )

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_package_without_auth_returns_401(client: AsyncClient):
    """인증 없이 패키지 생성 시 401을 반환한다."""
    res = await client.post(PACKAGE_BASE_URL, json=_make_package_payload())

    assert res.status_code == 401


# ===========================================================================
# 패키지 목록 조회
# ===========================================================================


@pytest.mark.asyncio
async def test_list_packages_returns_200_with_pagination(client: AsyncClient, fake):
    """패키지 목록 조회 시 200과 페이지네이션 정보를 반환한다."""
    user = await create_verified_user(client, fake)

    # 패키지 2개 생성
    await _create_package(client, user["headers"], name="vim")
    await _create_package(client, user["headers"], name="emacs", display_name="Emacs", category="editor")

    res = await client.get(PACKAGE_BASE_URL)

    assert res.status_code == 200
    data = res.json()["data"]
    assert "packages" in data
    assert "pagination" in data
    assert data["pagination"]["total_count"] == 2
    assert len(data["packages"]) == 2


@pytest.mark.asyncio
async def test_list_packages_with_category_filter(client: AsyncClient, fake):
    """카테고리 필터로 패키지 목록을 조회할 수 있다."""
    user = await create_verified_user(client, fake)

    await _create_package(client, user["headers"], name="vim", category="editor")
    await _create_package(
        client,
        user["headers"],
        name="htop",
        display_name="htop",
        category="system",
    )

    res = await client.get(f"{PACKAGE_BASE_URL}?category=editor")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["pagination"]["total_count"] == 1
    assert data["packages"][0]["category"] == "editor"


@pytest.mark.asyncio
async def test_list_packages_with_search(client: AsyncClient, fake):
    """검색어로 패키지를 필터링할 수 있다."""
    user = await create_verified_user(client, fake)

    await _create_package(client, user["headers"], name="neovim", display_name="Neovim")
    await _create_package(
        client,
        user["headers"],
        name="htop",
        display_name="htop",
        category="system",
    )

    res = await client.get(f"{PACKAGE_BASE_URL}?search=neovim")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["pagination"]["total_count"] == 1
    assert data["packages"][0]["name"] == "neovim"


@pytest.mark.asyncio
async def test_list_packages_empty_returns_200(client: AsyncClient):
    """패키지가 없을 때 빈 목록과 200을 반환한다."""
    res = await client.get(PACKAGE_BASE_URL)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["packages"] == []
    assert data["pagination"]["total_count"] == 0


# ===========================================================================
# 패키지 상세 조회
# ===========================================================================


@pytest.mark.asyncio
async def test_get_package_detail_returns_200(client: AsyncClient, fake):
    """패키지 상세 조회 시 200과 패키지 정보를 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.get(f"{PACKAGE_BASE_URL}{package_id}")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["package_id"] == package_id
    assert data["name"] == "neovim"
    assert data["display_name"] == "Neovim"
    assert data["category"] == "editor"
    assert "reviews_count" in data


@pytest.mark.asyncio
async def test_get_nonexistent_package_returns_404(client: AsyncClient):
    """존재하지 않는 패키지 조회 시 404를 반환한다."""
    res = await client.get(f"{PACKAGE_BASE_URL}99999")

    assert res.status_code == 404


# ===========================================================================
# 패키지 수정
# ===========================================================================


@pytest.mark.asyncio
async def test_update_package_by_author_returns_200(client: AsyncClient, fake):
    """작성자가 패키지를 수정하면 200을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.put(
        f"{PACKAGE_BASE_URL}{package_id}",
        json={"display_name": "Neovim (수정됨)", "description": "수정된 설명입니다."},
        headers=user["headers"],
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["display_name"] == "Neovim (수정됨)"
    assert data["description"] == "수정된 설명입니다."


@pytest.mark.asyncio
async def test_update_package_by_non_author_returns_403(client: AsyncClient, fake):
    """작성자가 아닌 사용자가 패키지를 수정하려 하면 403을 반환한다."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)
    package_id = await _create_package(client, user1["headers"])

    res = await client.put(
        f"{PACKAGE_BASE_URL}{package_id}",
        json={"display_name": "탈취 시도"},
        headers=user2["headers"],
    )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_update_any_package(client: AsyncClient, fake):
    """관리자는 타인의 패키지도 수정할 수 있다."""
    user = await create_verified_user(client, fake)
    admin = await create_admin_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.put(
        f"{PACKAGE_BASE_URL}{package_id}",
        json={"display_name": "관리자가 수정함"},
        headers=admin["headers"],
    )

    assert res.status_code == 200
    assert res.json()["data"]["display_name"] == "관리자가 수정함"


@pytest.mark.asyncio
async def test_update_nonexistent_package_returns_404(client: AsyncClient, fake):
    """존재하지 않는 패키지 수정 시 404를 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.put(
        f"{PACKAGE_BASE_URL}99999",
        json={"display_name": "존재하지 않는 패키지"},
        headers=user["headers"],
    )

    assert res.status_code == 404


# ===========================================================================
# 리뷰 생성
# ===========================================================================


@pytest.mark.asyncio
async def test_create_review_returns_201(client: AsyncClient, fake):
    """유효한 데이터로 리뷰 생성 시 201을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    res = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(),
        headers=reviewer["headers"],
    )

    assert res.status_code == 201
    data = res.json()["data"]
    assert "review_id" in data
    assert data["review_id"] > 0


@pytest.mark.asyncio
async def test_create_review_with_min_rating(client: AsyncClient, fake):
    """rating=1로 리뷰 생성이 가능하다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    res = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(rating=1),
        headers=reviewer["headers"],
    )

    assert res.status_code == 201


@pytest.mark.asyncio
async def test_create_review_with_invalid_rating_returns_422(client: AsyncClient, fake):
    """유효하지 않은 rating(0 또는 6)으로 리뷰 생성 시 422를 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)

    # rating=0 (최소값 미만)
    res = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(rating=0),
        headers=reviewer["headers"],
    )
    assert res.status_code == 422

    # rating=6 (최대값 초과)
    res2 = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(rating=6),
        headers=reviewer["headers"],
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_review_returns_409(client: AsyncClient, fake):
    """동일 사용자가 같은 패키지에 중복 리뷰를 작성하면 409를 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)

    # 첫 번째 리뷰 — 성공
    res1 = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(),
        headers=reviewer["headers"],
    )
    assert res1.status_code == 201

    # 두 번째 리뷰 — 중복
    res2 = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(title="두 번째 리뷰", content="중복 리뷰를 시도합니다. 이것은 실패해야 합니다."),
        headers=reviewer["headers"],
    )
    assert res2.status_code == 409
    assert res2.json()["detail"]["error"] == "REVIEW_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_review_without_auth_returns_401(client: AsyncClient, fake):
    """인증 없이 리뷰 생성 시 401을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.post(
        f"{PACKAGE_BASE_URL}{package_id}/reviews",
        json=_make_review_payload(),
    )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_review_for_nonexistent_package_returns_404(client: AsyncClient, fake):
    """존재하지 않는 패키지에 리뷰를 작성하면 404를 반환한다."""
    user = await create_verified_user(client, fake)

    res = await client.post(
        f"{PACKAGE_BASE_URL}99999/reviews",
        json=_make_review_payload(),
        headers=user["headers"],
    )

    assert res.status_code == 404


# ===========================================================================
# 리뷰 목록 조회
# ===========================================================================


@pytest.mark.asyncio
async def test_list_reviews_returns_200_with_pagination(client: AsyncClient, fake):
    """리뷰 목록 조회 시 200과 페이지네이션 정보를 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    # 두 명의 리뷰어가 각각 리뷰 작성
    reviewer1 = await create_verified_user(client, fake)
    reviewer2 = await create_verified_user(client, fake)
    await _create_review(client, reviewer1["headers"], package_id)
    await _create_review(
        client,
        reviewer2["headers"],
        package_id,
        rating=3,
        title="보통입니다",
        content="사용해볼 만하지만 아쉬운 점도 있습니다.",
    )

    res = await client.get(f"{PACKAGE_BASE_URL}{package_id}/reviews")

    assert res.status_code == 200
    data = res.json()["data"]
    assert "reviews" in data
    assert "pagination" in data
    assert data["pagination"]["total_count"] == 2
    assert len(data["reviews"]) == 2


@pytest.mark.asyncio
async def test_list_reviews_empty_returns_200(client: AsyncClient, fake):
    """리뷰가 없는 패키지의 리뷰 목록 조회 시 빈 목록과 200을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.get(f"{PACKAGE_BASE_URL}{package_id}/reviews")

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["reviews"] == []
    assert data["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_reviews_for_nonexistent_package_returns_404(client: AsyncClient, fake):
    """존재하지 않는 패키지의 리뷰 목록 조회 시 404를 반환한다."""
    res = await client.get(f"{PACKAGE_BASE_URL}99999/reviews")

    assert res.status_code == 404


# ===========================================================================
# 리뷰 수정
# ===========================================================================


@pytest.mark.asyncio
async def test_update_review_by_author_returns_200(client: AsyncClient, fake):
    """작성자가 리뷰를 수정하면 200을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    review_id = await _create_review(client, reviewer["headers"], package_id)

    res = await client.put(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/{review_id}",
        json={
            "rating": 4,
            "title": "수정된 리뷰 제목",
            "content": "수정된 리뷰 내용입니다. 충분히 긴 내용을 포함합니다.",
        },
        headers=reviewer["headers"],
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["rating"] == 4
    assert data["title"] == "수정된 리뷰 제목"


@pytest.mark.asyncio
async def test_update_review_by_non_author_returns_403(client: AsyncClient, fake):
    """작성자가 아닌 사용자가 리뷰를 수정하려 하면 403을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    review_id = await _create_review(client, reviewer["headers"], package_id)

    other_user = await create_verified_user(client, fake)
    res = await client.put(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/{review_id}",
        json={"rating": 1},
        headers=other_user["headers"],
    )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_update_nonexistent_review_returns_404(client: AsyncClient, fake):
    """존재하지 않는 리뷰 수정 시 404를 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.put(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/99999",
        json={"rating": 3},
        headers=user["headers"],
    )

    assert res.status_code == 404


# ===========================================================================
# 리뷰 삭제
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_review_by_author_returns_200(client: AsyncClient, fake):
    """작성자가 리뷰를 삭제하면 200을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    review_id = await _create_review(client, reviewer["headers"], package_id)

    res = await client.delete(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/{review_id}",
        headers=reviewer["headers"],
    )

    assert res.status_code == 200

    # 삭제 후 리뷰 목록에서 제거되었는지 확인 (soft delete)
    list_res = await client.get(f"{PACKAGE_BASE_URL}{package_id}/reviews")
    assert list_res.status_code == 200
    assert list_res.json()["data"]["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_delete_review_by_non_author_returns_403(client: AsyncClient, fake):
    """작성자가 아닌 사용자가 리뷰를 삭제하려 하면 403을 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    review_id = await _create_review(client, reviewer["headers"], package_id)

    other_user = await create_verified_user(client, fake)
    res = await client.delete(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/{review_id}",
        headers=other_user["headers"],
    )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_delete_any_review(client: AsyncClient, fake):
    """관리자는 타인의 리뷰도 삭제할 수 있다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    review_id = await _create_review(client, reviewer["headers"], package_id)

    admin = await create_admin_user(client, fake)
    res = await client.delete(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/{review_id}",
        headers=admin["headers"],
    )

    assert res.status_code == 200


@pytest.mark.asyncio
async def test_delete_nonexistent_review_returns_404(client: AsyncClient, fake):
    """존재하지 않는 리뷰 삭제 시 404를 반환한다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.delete(
        f"{PACKAGE_BASE_URL}{package_id}/reviews/99999",
        headers=user["headers"],
    )

    assert res.status_code == 404


# ===========================================================================
# 권한: 미인증 사용자의 읽기 접근
# ===========================================================================


@pytest.mark.asyncio
async def test_unauthenticated_user_can_list_packages(client: AsyncClient, fake):
    """미인증 사용자도 패키지 목록을 조회할 수 있다."""
    user = await create_verified_user(client, fake)
    await _create_package(client, user["headers"])

    # 인증 헤더 없이 조회
    res = await client.get(PACKAGE_BASE_URL)

    assert res.status_code == 200
    assert len(res.json()["data"]["packages"]) == 1


@pytest.mark.asyncio
async def test_unauthenticated_user_can_get_package_detail(client: AsyncClient, fake):
    """미인증 사용자도 패키지 상세를 조회할 수 있다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    res = await client.get(f"{PACKAGE_BASE_URL}{package_id}")

    assert res.status_code == 200
    assert res.json()["data"]["package_id"] == package_id


@pytest.mark.asyncio
async def test_unauthenticated_user_can_list_reviews(client: AsyncClient, fake):
    """미인증 사용자도 리뷰 목록을 조회할 수 있다."""
    user = await create_verified_user(client, fake)
    package_id = await _create_package(client, user["headers"])

    reviewer = await create_verified_user(client, fake)
    await _create_review(client, reviewer["headers"], package_id)

    # 인증 헤더 없이 조회
    res = await client.get(f"{PACKAGE_BASE_URL}{package_id}/reviews")

    assert res.status_code == 200
    assert len(res.json()["data"]["reviews"]) == 1
