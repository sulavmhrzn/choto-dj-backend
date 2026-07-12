from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.analytics.models import ClickEvent
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


@pytest.fixture
def short_link(user: User) -> ShortLink:
    return ShortLink.objects.create(
        owner=user,
        short_code="stats01",
        destination_url="https://example.com",
    )


@pytest.mark.django_db
def test_link_analytics_returns_summary(
    authenticated_client: APIClient,
    short_link: ShortLink,
) -> None:
    recent_click = ClickEvent.objects.create(
        short_link=short_link,
        referrer="https://google.com",
        user_agent="Test Browser",
        ip_address="127.0.0.1",
    )

    old_click = ClickEvent.objects.create(
        short_link=short_link,
        referrer="https://example.com",
    )

    ClickEvent.objects.filter(id=old_click.id).update(
        clicked_at=timezone.now() - timedelta(days=2)
    )

    response = authenticated_client.get(
        reverse(
            "analytics:short-link",
            kwargs={"link_id": short_link.id},
        )
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_clicks"] == 2
    assert response.data["clicks_today"] == 1
    assert len(response.data["recent_clicks"]) == 2

    first_click = response.data["recent_clicks"][0]

    assert first_click["id"] == str(recent_click.id)
    assert first_click["referrer"] == "https://google.com"
    assert first_click["user_agent"] == "Test Browser"
    assert first_click["ip_address"] == "127.0.0.1"


@pytest.mark.django_db
def test_user_cannot_view_another_users_analytics(
    authenticated_client: APIClient,
    another_user: User,
) -> None:
    link = ShortLink.objects.create(
        owner=another_user,
        short_code="private2",
        destination_url="https://example.com/private",
    )

    ClickEvent.objects.create(short_link=link)

    response = authenticated_client.get(
        reverse(
            "analytics:short-link",
            kwargs={"link_id": link.id},
        )
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_link_analytics_requires_authentication(
    api_client: APIClient,
    short_link: ShortLink,
) -> None:
    response = api_client.get(
        reverse(
            "analytics:short-link",
            kwargs={"link_id": short_link.id},
        )
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_link_analytics_returns_zero_when_no_clicks(
    authenticated_client: APIClient,
    short_link: ShortLink,
) -> None:
    response = authenticated_client.get(
        reverse(
            "analytics:short-link",
            kwargs={"link_id": short_link.id},
        )
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "total_clicks": 0,
        "clicks_today": 0,
        "recent_clicks": [],
    }
