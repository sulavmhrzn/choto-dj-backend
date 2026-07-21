from unittest.mock import Mock

import pytest
from psycopg.generators import execute

from apps.accounts.models import User
from apps.links import services
from apps.links.services import short_link_create


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
