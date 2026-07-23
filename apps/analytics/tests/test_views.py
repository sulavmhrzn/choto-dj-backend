from datetime import datetime, time, timedelta

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
        ip_address="127.0.0.2",
    )

    old_clicked_at = timezone.now() - timedelta(days=2)

    ClickEvent.objects.filter(id=old_click.id).update(
        clicked_at=old_clicked_at,
    )

    old_click.refresh_from_db()

    response = authenticated_client.get(
        reverse(
            "analytics:short-link",
            kwargs={"link_id": short_link.id},
        )
    )

    assert response.status_code == status.HTTP_200_OK

    assert response.data["total_clicks"] == 2
    assert response.data["clicks_today"] == 1
    assert response.data["unique_visitors"] == 2

    assert response.data["first_clicked_at"] == old_click.clicked_at

    assert response.data["last_clicked_at"] == recent_click.clicked_at

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
    assert response.data["total_clicks"] == 0
    assert response.data["clicks_today"] == 0
    assert response.data["unique_visitors"] == 0
    assert response.data["first_clicked_at"] is None
    assert response.data["last_clicked_at"] is None
    assert response.data["recent_clicks"] == []

    clicks_over_time = response.data["clicks_over_time"]

    assert len(clicks_over_time) == 30

    assert clicks_over_time[0] == {
        "date": timezone.localdate() - timedelta(days=29),
        "clicks": 0,
    }
    assert clicks_over_time[-1] == {
        "date": timezone.localdate(),
        "clicks": 0,
    }
    assert all(item["clicks"] == 0 for item in clicks_over_time)


@pytest.mark.django_db
def test_link_analytics_counts_distinct_non_null_ip_addresses(
    authenticated_client: APIClient,
    short_link: ShortLink,
) -> None:
    ClickEvent.objects.create(
        short_link=short_link,
        ip_address="127.0.0.1",
    )
    ClickEvent.objects.create(
        short_link=short_link,
        ip_address="127.0.0.1",
    )
    ClickEvent.objects.create(
        short_link=short_link,
        ip_address="127.0.0.2",
    )
    ClickEvent.objects.create(
        short_link=short_link,
        ip_address=None,
    )

    response = authenticated_client.get(
        reverse(
            "analytics:short-link",
            kwargs={"link_id": short_link.id},
        )
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_clicks"] == 4
    assert response.data["unique_visitors"] == 2


@pytest.mark.django_db
def test_link_analytics_returns_clicks_over_time(authenticated_client, short_link):
    today = timezone.localdate()
    first_date = today - timedelta(days=2)
    second_date = today - timedelta(days=1)

    first_timestamp = timezone.make_aware(datetime.combine(first_date, time(hour=12)))
    second_timestamp = timezone.make_aware(datetime.combine(second_date, time(hour=12)))

    first_click = ClickEvent.objects.create(short_link=short_link)
    second_click = ClickEvent.objects.create(short_link=short_link)
    third_click = ClickEvent.objects.create(short_link=short_link)

    ClickEvent.objects.filter(id=first_click.id).update(clicked_at=first_timestamp)
    ClickEvent.objects.filter(id=second_click.id).update(
        clicked_at=first_timestamp + timedelta(hours=1)
    )
    ClickEvent.objects.filter(id=third_click.id).update(clicked_at=second_timestamp)

    response = authenticated_client.get(
        reverse("analytics:short-link", kwargs={"link_id": short_link.id})
    )

    assert response.status_code == status.HTTP_200_OK

    clicks_over_time = response.data["clicks_over_time"]

    assert len(clicks_over_time) == 30

    counts_by_date = {item["date"]: item["clicks"] for item in clicks_over_time}

    assert counts_by_date[first_date] == 2
    assert counts_by_date[second_date] == 1
    assert counts_by_date[today] == 0

    assert clicks_over_time[0]["date"] == today - timedelta(days=29)
    assert clicks_over_time[-1]["date"] == today
