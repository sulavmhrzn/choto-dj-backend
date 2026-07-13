from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User
from apps.links.cache import short_link_redirect_cache_key
from apps.links.models import ShortLink
from apps.links.selectors import short_link_get_redirectable_by_code
from apps.links.services import short_link_create, short_link_delete, short_link_update

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
def user(db):
    return User.objects.create_user(
        email="owner@example.com", full_name="Test owner", password="test-password"
    )


@pytest.fixture
def short_link(user):
    return ShortLink.objects.create(
        owner=user,
        short_code="abc123",
        destination_url="https://example.com",
        title="Example link",
        is_active=True,
    )


def test_redirect_lookup_queries_database_on_cache_miss(
    short_link, django_assert_num_queries
):
    with django_assert_num_queries(1):
        result = short_link_get_redirectable_by_code(short_code=short_link.short_code)
    assert result is not None
    assert result.id == short_link.id
    assert result.destination_url == short_link.destination_url


def test_redirect_lookup_uses_cache_after_first_lookup(
    short_link, django_assert_num_queries
):
    first_result = short_link_get_redirectable_by_code(short_code=short_link.short_code)

    assert first_result is not None

    with django_assert_num_queries(0):
        second_result = short_link_get_redirectable_by_code(
            short_code=short_link.short_code
        )

    assert second_result is not None
    assert second_result.id == short_link.id
    assert second_result.destination_url == short_link.destination_url


@pytest.mark.django_db
def test_missing_short_link_is_negatively_cached(django_assert_num_queries):
    with django_assert_num_queries(1):
        first_result = short_link_get_redirectable_by_code(short_code="missing-code")

    assert first_result is None

    with django_assert_num_queries(0):
        second_result = short_link_get_redirectable_by_code(short_code="missing-code")

    assert second_result is None


def test_short_link_update_invalidates_redirect_cache(
    short_link, django_assert_num_queries
):
    original_result = short_link_get_redirectable_by_code(
        short_code=short_link.short_code
    )

    assert original_result is not None

    updated_destination = "https://example.com/updated"
    short_link_update(link=short_link, destination_url=updated_destination)

    with django_assert_num_queries(1):
        updated_result = short_link_get_redirectable_by_code(
            short_code=short_link.short_code
        )
    assert updated_result is not None
    assert updated_result.destination_url == updated_destination


def test_short_link_deactivation_invalidates_redirect_cache(
    short_link,
    django_assert_num_queries,
):
    cached_result = short_link_get_redirectable_by_code(
        short_code=short_link.short_code,
    )

    assert cached_result is not None

    short_link_update(
        link=short_link,
        is_active=False,
    )

    with django_assert_num_queries(1):
        result = short_link_get_redirectable_by_code(
            short_code=short_link.short_code,
        )

    assert result is None


def test_short_link_delete_invalidates_redirect_cache(
    short_link,
    django_assert_num_queries,
):
    cached_result = short_link_get_redirectable_by_code(
        short_code=short_link.short_code,
    )

    assert cached_result is not None

    short_code = short_link.short_code

    short_link_delete(link=short_link)

    with django_assert_num_queries(1):
        result = short_link_get_redirectable_by_code(
            short_code=short_code,
        )

    assert result is None


def test_short_link_create_clears_negative_cache(
    user,
    django_assert_num_queries,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    short_code = "abc123"

    missing_result = short_link_get_redirectable_by_code(short_code=short_code)

    assert missing_result is None

    monkeypatch.setattr("apps.links.services.generate_short_code", lambda: short_code)

    with django_capture_on_commit_callbacks(execute=True):
        link = short_link_create(owner=user, destination_url="https://example.com")

    with django_assert_num_queries(1):
        result = short_link_get_redirectable_by_code(short_code=short_code)

    assert result is not None
    assert result.id == link.id
