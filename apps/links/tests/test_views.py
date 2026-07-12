from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.links.models import ShortLink


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
