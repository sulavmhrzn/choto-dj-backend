from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.models import ClickEvent
from apps.analytics.selectors import click_event_get_daily_counts
from apps.links.models import ShortLink


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@mail.com",
        password="sulavmhrzn",
    )


@pytest.fixture
def short_link(user) -> ShortLink:
    return ShortLink.objects.create(
        owner=user, title="Example", destination_url="https://example.com"
    )


@pytest.mark.django_db
def test_click_event_get_daily_counts_groups_clicks_by_date(
    short_link,
):
    today = timezone.localdate()
    first_date = today - timedelta(days=2)
    second_date = today - timedelta(days=1)

    first_timestamp = timezone.make_aware(
        datetime.combine(
            first_date,
            time(hour=12),
        )
    )
    second_timestamp = timezone.make_aware(
        datetime.combine(
            second_date,
            time(hour=12),
        )
    )

    first_click = ClickEvent.objects.create(short_link=short_link)
    second_click = ClickEvent.objects.create(short_link=short_link)
    third_click = ClickEvent.objects.create(short_link=short_link)

    ClickEvent.objects.filter(id=first_click.id).update(clicked_at=first_timestamp)
    ClickEvent.objects.filter(id=second_click.id).update(
        clicked_at=first_timestamp + timedelta(hours=1)
    )
    ClickEvent.objects.filter(id=third_click.id).update(clicked_at=second_timestamp)

    start_at = timezone.make_aware(
        datetime.combine(first_date - timedelta(days=1), time.min)
    )

    results = list(
        click_event_get_daily_counts(
            short_link=short_link,
            start_at=start_at,
        )
    )

    assert results == [
        {
            "date": first_date,
            "clicks": 2,
        },
        {
            "date": second_date,
            "clicks": 1,
        },
    ]
