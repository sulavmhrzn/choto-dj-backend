from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.links import services
from apps.links.models import ShortLink
from apps.links.services import short_link_create, short_link_deactivate_expired


@pytest.fixture
def user() -> User:
    return User.objects.create_user(email="sulav@mail.com", password="strong-password")


@pytest.mark.django_db
def test_short_link_create_rejects_duplicate_custom_alias(user):
    short_link_create(
        owner=user,
        destination_url="https://example.com/first",
        short_code="portfolio",
    )

    with pytest.raises(
        ValueError,
        match="This custom alias is already in use.",
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com/second",
            short_code="portfolio",
        )


@pytest.mark.django_db
def test_short_link_create_runs_side_effects_after_commit(
    user, monkeypatch, django_capture_on_commit_callbacks
):
    cache_delete_mock = Mock()
    metric_increment_mock = Mock()

    monkeypatch.setattr(services, "short_link_redirect_cache_delete", cache_delete_mock)
    monkeypatch.setattr(
        services.short_links_created_total, "inc", metric_increment_mock
    )

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        link = short_link_create(
            owner=user,
            destination_url="https://example.com",
            title="Example",
        )

        cache_delete_mock.assert_not_called()
        metric_increment_mock.assert_not_called()

    assert len(callbacks) == 1
    callbacks[0]()

    cache_delete_mock.assert_called_once_with(short_code=link.short_code)
    metric_increment_mock.assert_called_once_with()


@pytest.mark.django_db
def test_short_link_deactivate_expired_deactivates_only_expired_active_links(
    user, monkeypatch, django_capture_on_commit_callbacks
):
    now = timezone.now()

    expired_link = ShortLink.objects.create(
        owner=user,
        short_code="expired-link",
        destination_url="https://example.com/expired",
        is_active=True,
        expires_at=now - timedelta(minutes=1),
    )

    future_link = ShortLink.objects.create(
        owner=user,
        short_code="future-link",
        destination_url="https://example.com/future",
        is_active=True,
        expires_at=now + timedelta(days=3),
    )

    inactive_expired_link = ShortLink.objects.create(
        owner=user,
        short_code="inactive-expired",
        destination_url="https://example.com/inactive",
        is_active=False,
        expires_at=now - timedelta(days=3),
    )

    non_expiring_link = ShortLink.objects.create(
        owner=user,
        short_code="never-expires",
        destination_url="https://example.com/permanent",
        is_active=True,
        expires_at=None,
    )

    cache_delete_mock = Mock()

    monkeypatch.setattr(services, "short_link_redirect_cache_delete", cache_delete_mock)

    with django_capture_on_commit_callbacks(execute=True):
        updated_count = short_link_deactivate_expired()

    assert updated_count == 1

    expired_link.refresh_from_db()
    future_link.refresh_from_db()
    inactive_expired_link.refresh_from_db()
    non_expiring_link.refresh_from_db()

    assert expired_link.is_active is False
    assert future_link.is_active is True
    assert inactive_expired_link.is_active is False
    assert non_expiring_link.is_active is True

    cache_delete_mock.assert_called_once_with(short_code=expired_link.short_code)


@pytest.mark.django_db
def test_short_link_deactivate_expired_returns_zero_when_none_exist(
    user,
    monkeypatch,
):
    ShortLink.objects.create(
        owner=user,
        short_code="future-link",
        destination_url="https://example.com",
        is_active=True,
        expires_at=timezone.now() + timedelta(days=1),
    )

    cache_delete_mock = Mock()

    monkeypatch.setattr(
        services,
        "short_link_redirect_cache_delete",
        cache_delete_mock,
    )

    updated_count = short_link_deactivate_expired()

    assert updated_count == 0
    cache_delete_mock.assert_not_called()
