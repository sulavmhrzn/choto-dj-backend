from datetime import timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.links.models import ShortLink
from apps.links.services import short_link_create

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "choto-tests",
    }
}


@pytest.fixture(autouse=True)
def use_test_cache(settings):
    settings.CACHES = TEST_CACHES
    settings.SHORT_LINK_CACHE_TIMEOUT = 300

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@example.com",
        password="strong-password",
    )


@pytest.fixture
def another_user() -> User:
    return User.objects.create_user(
        email="another@example.com",
        password="strong-password",
    )


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_client(
    api_client: APIClient,
    user: User,
) -> APIClient:
    refresh = RefreshToken.for_user(user)

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    return api_client


@pytest.mark.django_db
def test_user_can_create_short_link(
    authenticated_client: APIClient,
    user: User,
) -> None:
    response = authenticated_client.post(
        reverse("links:list-create"),
        data={
            "destination_url": "https://example.com/articles/django",
            "title": "Django article",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    link = ShortLink.objects.get()

    assert link.owner == user
    assert link.destination_url == "https://example.com/articles/django"
    assert link.title == "Django article"
    assert link.short_code
    assert response.data["short_code"] == link.short_code


@pytest.mark.django_db
def test_anonymous_user_cannot_create_short_link(
    api_client: APIClient,
) -> None:
    response = api_client.post(
        reverse("links:list-create"),
        data={
            "destination_url": "https://example.com",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert ShortLink.objects.exists() is False


@pytest.mark.django_db
def test_user_cannot_access_another_users_link(
    authenticated_client: APIClient,
    another_user: User,
) -> None:
    link = ShortLink.objects.create(
        owner=another_user,
        short_code="private1",
        destination_url="https://example.com/private",
    )

    response = authenticated_client.get(
        reverse(
            "links:detail",
            kwargs={"link_id": link.id},
        )
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_active_short_link_redirects(
    api_client: APIClient,
    user: User,
) -> None:
    link = ShortLink.objects.create(
        owner=user,
        short_code="active1",
        destination_url="https://example.com/destination",
    )

    response = api_client.get(
        reverse(
            "short-link-redirect",
            kwargs={"short_code": link.short_code},
        )
    )

    assert response.status_code == status.HTTP_302_FOUND
    assert response["Location"] == link.destination_url


@pytest.mark.django_db
def test_inactive_short_link_returns_not_found(
    api_client: APIClient,
    user: User,
) -> None:
    link = ShortLink.objects.create(
        owner=user,
        short_code="inactive1",
        destination_url="https://example.com/destination",
        is_active=False,
    )

    response = api_client.get(
        reverse(
            "short-link-redirect",
            kwargs={"short_code": link.short_code},
        )
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_expired_short_link_returns_not_found(
    api_client: APIClient,
    user: User,
) -> None:
    link = ShortLink.objects.create(
        owner=user,
        short_code="expired1",
        destination_url="https://example.com/destination",
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    response = api_client.get(
        reverse(
            "short-link-redirect",
            kwargs={"short_code": link.short_code},
        )
    )

    @pytest.mark.django_db
    def test_unexpired_short_link_redirects(
        api_client: APIClient,
        user: User,
    ) -> None:
        link = ShortLink.objects.create(
            owner=user,
            short_code="future1",
            destination_url="https://example.com/destination",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = api_client.get(
            reverse(
                "short-link-redirect",
                kwargs={"short_code": link.short_code},
            )
        )

        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == link.destination_url

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_authenticated_user_can_create_link_with_custom_alias(
    authenticated_client,
):
    response = authenticated_client.post(
        reverse("links:list-create"),
        data={
            "destination_url": "https://example.com",
            "title": "Portfolio",
            "short_code": "my-portfolio",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["short_code"] == "my-portfolio"


@pytest.mark.django_db
def test_duplicate_custom_alias_returns_400(
    authenticated_client,
):
    url = reverse("links:list-create")

    first_response = authenticated_client.post(
        url,
        data={
            "destination_url": "https://example.com/first",
            "short_code": "portfolio",
        },
        format="json",
    )

    second_response = authenticated_client.post(
        url,
        data={
            "destination_url": "https://example.com/second",
            "short_code": "portfolio",
        },
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.data["errors"]["short_code"] == (
        "This custom alias is already in use."
    )


@pytest.mark.django_db
def test_custom_alias_redirects_to_destination(
    api_client,
    user,
):
    short_link_create(
        owner=user,
        destination_url="https://example.com/portfolio",
        short_code="my-portfolio",
    )

    response = api_client.get("/my-portfolio/")

    assert response.status_code == 302
    assert response.url == "https://example.com/portfolio"


@pytest.mark.django_db
def test_short_link_list_is_paginated(
    authenticated_client,
    user,
):
    for index in range(3):
        ShortLink.objects.create(
            owner=user,
            short_code=f"link{index}",
            destination_url=f"https://example.com/{index}",
        )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"page_size": 2},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["count"] == 3
    assert len(body["data"]["results"]) == 2
    assert body["data"]["next"] is not None


@pytest.mark.django_db
def test_short_link_list_filters_active_links(
    authenticated_client,
    user,
):
    active_link = ShortLink.objects.create(
        owner=user,
        short_code="active-link",
        title="Active link",
        is_active=True,
    )
    ShortLink.objects.create(
        owner=user,
        short_code="inactive-link",
        title="Inactive link",
        is_active=False,
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"is_active": "true"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(active_link.id)


@pytest.mark.django_db
def test_short_link_list_filters_active_links(
    authenticated_client,
    user,
):
    active_link = ShortLink.objects.create(
        owner=user,
        short_code="active-link",
        title="Active link",
        is_active=True,
    )
    ShortLink.objects.create(
        owner=user,
        short_code="inactive-link",
        title="Inactive link",
        is_active=False,
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"is_active": "true"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(active_link.id)


@pytest.mark.django_db
def test_short_link_list_filters_inactive_links(
    authenticated_client,
    user,
):
    ShortLink.objects.create(
        owner=user,
        short_code="active-link",
        title="Active link",
        is_active=True,
    )
    inactive_link = ShortLink.objects.create(
        owner=user,
        short_code="inactive-link",
        title="Inactive link",
        is_active=False,
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"is_active": "false"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(inactive_link.id)


@pytest.mark.django_db
def test_short_link_list_searches_by_title(
    authenticated_client,
    user,
):
    matching_link = ShortLink.objects.create(
        owner=user,
        short_code="portfolio",
        title="My Developer Portfolio",
    )
    ShortLink.objects.create(
        owner=user,
        short_code="documentation",
        title="Project documentation",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"search": "developer"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(matching_link.id)


@pytest.mark.django_db
def test_short_link_list_searches_by_short_code(
    authenticated_client,
    user,
):
    matching_link = ShortLink.objects.create(
        owner=user,
        short_code="github-profile",
        title="Profile",
    )
    ShortLink.objects.create(
        owner=user,
        short_code="portfolio",
        title="Portfolio",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"search": "github"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(matching_link.id)


@pytest.mark.django_db
def test_short_link_list_searches_by_destination_url(
    authenticated_client,
    user,
):
    matching_link = ShortLink.objects.create(
        owner=user,
        short_code="django-docs",
        title="Documentation",
        destination_url="https://docs.djangoproject.com/",
    )
    ShortLink.objects.create(
        owner=user,
        short_code="python-docs",
        title="Python",
        destination_url="https://docs.python.org/",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"search": "djangoproject"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(matching_link.id)


@pytest.mark.django_db
def test_short_link_list_search_is_case_insensitive(
    authenticated_client,
    user,
):
    matching_link = ShortLink.objects.create(
        owner=user,
        short_code="portfolio",
        title="Developer Portfolio",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"search": "DEVELOPER"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["data"]["count"] == 1
    assert body["data"]["results"][0]["id"] == str(matching_link.id)


@pytest.mark.django_db
def test_short_link_list_orders_by_title(
    authenticated_client,
    user,
):
    ShortLink.objects.create(
        owner=user,
        short_code="z-link",
        title="Zulu",
    )
    ShortLink.objects.create(
        owner=user,
        short_code="a-link",
        title="Alpha",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"ordering": "title"},
    )

    assert response.status_code == 200

    results = response.json()["data"]["results"]

    assert [result["title"] for result in results] == [
        "Alpha",
        "Zulu",
    ]


@pytest.mark.django_db
def test_short_link_list_orders_by_title_descending(
    authenticated_client,
    user,
):
    ShortLink.objects.create(
        owner=user,
        short_code="a-link",
        title="Alpha",
    )
    ShortLink.objects.create(
        owner=user,
        short_code="z-link",
        title="Zulu",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"ordering": "-title"},
    )

    assert response.status_code == 200

    results = response.json()["data"]["results"]

    assert [result["title"] for result in results] == [
        "Zulu",
        "Alpha",
    ]


@pytest.mark.django_db
def test_short_link_list_rejects_invalid_ordering(
    authenticated_client,
):
    response = authenticated_client.get(
        reverse("links:list-create"),
        {"ordering": "owner"},
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert body["data"] is None
    assert "ordering" in body["errors"]


@pytest.mark.django_db
def test_short_link_list_rejects_invalid_is_active_value(
    authenticated_client,
):
    response = authenticated_client.get(
        reverse("links:list-create"),
        {"is_active": "sometimes"},
    )

    assert response.status_code == 400

    body = response.json()

    assert body["success"] is False
    assert "is_active" in body["errors"]


@pytest.mark.django_db
def test_short_link_list_combines_search_and_active_filter(
    authenticated_client,
    user,
):
    matching_link = ShortLink.objects.create(
        owner=user,
        short_code="active-portfolio",
        title="Portfolio",
        is_active=True,
    )
    ShortLink.objects.create(
        owner=user,
        short_code="inactive-portfolio",
        title="Portfolio",
        is_active=False,
    )
    ShortLink.objects.create(
        owner=user,
        short_code="active-docs",
        title="Documentation",
        is_active=True,
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {
            "search": "portfolio",
            "is_active": "true",
        },
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(matching_link.id)


@pytest.mark.django_db
def test_short_link_filters_do_not_include_another_users_links(
    authenticated_client,
    user,
    another_user,
):
    own_link = ShortLink.objects.create(
        owner=user,
        short_code="my-portfolio",
        title="Portfolio",
    )
    ShortLink.objects.create(
        owner=another_user,
        short_code="other-portfolio",
        title="Portfolio",
    )

    response = authenticated_client.get(
        reverse("links:list-create"),
        {"search": "portfolio"},
    )

    assert response.status_code == 200

    body = response.json()
    results = body["data"]["results"]

    assert body["data"]["count"] == 1
    assert results[0]["id"] == str(own_link.id)


@pytest.mark.django_db
def test_short_link_creation_is_throttled(
    authenticated_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {
            **ScopedRateThrottle.THROTTLE_RATES,
            "short_link_create": "2/minute",
        },
    )
    url = reverse("links:list-create")

    payloads = [
        {"destination_url": "https://example.com/1"},
        {"destination_url": "https://example.com/2"},
        {"destination_url": "https://example.com/3"},
    ]

    first_response = authenticated_client.post(url, payloads[0], format="json")
    second_response = authenticated_client.post(url, payloads[1], format="json")
    third_response = authenticated_client.post(url, payloads[2], format="json")

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    assert third_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert third_response.data["success"] is False
    assert "Retry-After" in third_response


@pytest.mark.django_db
def test_short_link_list_is_not_affected_by_creation_throttle(
    authenticated_client: APIClient,
) -> None:
    url = reverse("links:list-create")

    for _ in range(3):
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
