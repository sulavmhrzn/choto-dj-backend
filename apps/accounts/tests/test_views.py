from sys import thread_info

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

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
        full_name="Sulav Maharjan",
        avatar_url="https://example.com/avatar.jpg",
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
    access_token = str(refresh.access_token)

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    return api_client


@pytest.mark.django_db
def test_user_me_requires_authentication(
    api_client: APIClient,
) -> None:
    url = reverse("accounts:me")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_user_me_returns_authenticated_user(
    authenticated_client: APIClient,
    user: User,
) -> None:
    url = reverse("accounts:me")

    response = authenticated_client.get(url)

    assert response.status_code == status.HTTP_200_OK

    assert response.data["id"] == str(user.id)
    assert response.data["email"] == user.email
    assert response.data["full_name"] == user.full_name
    assert response.data["avatar_url"] == user.avatar_url
    assert "date_joined" in response.data


@pytest.mark.django_db
def test_user_me_updates_profile(
    authenticated_client: APIClient,
    user: User,
) -> None:
    url = reverse("accounts:me")

    payload = {
        "full_name": "Updated Name",
        "avatar_url": "https://example.com/new-avatar.jpg",
    }

    response = authenticated_client.patch(
        url,
        data=payload,
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.full_name == "Updated Name"
    assert user.avatar_url == "https://example.com/new-avatar.jpg"

    assert response.data["full_name"] == "Updated Name"
    assert response.data["avatar_url"] == "https://example.com/new-avatar.jpg"


@pytest.mark.django_db
def test_user_me_updates_only_provided_fields(
    authenticated_client: APIClient,
    user: User,
) -> None:
    url = reverse("accounts:me")

    original_avatar_url = user.avatar_url

    response = authenticated_client.patch(
        url,
        data={"full_name": "Only Name Changed"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.refresh_from_db()

    assert user.full_name == "Only Name Changed"
    assert user.avatar_url == original_avatar_url


@pytest.mark.django_db
def test_user_me_rejects_empty_update(
    authenticated_client: APIClient,
) -> None:
    url = reverse("accounts:me")

    response = authenticated_client.patch(
        url,
        data={},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data["errors"]


@pytest.mark.django_db
def test_user_me_rejects_invalid_avatar_url(
    authenticated_client: APIClient,
) -> None:
    url = reverse("accounts:me")

    response = authenticated_client.patch(
        url,
        data={"avatar_url": "invalid-url"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "avatar_url" in response.data["errors"]


@pytest.mark.django_db
def test_login_is_throttled_after_repeated_failed_attempts(
    api_client,
    user,
    monkeypatch,
):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {
            **ScopedRateThrottle.THROTTLE_RATES,
            "login": "2/minute",
        },
    )

    payload = {
        "email": user.email,
        "password": "incorrect-password",
    }

    first_response = api_client.post(
        "/api/v1/auth/token/",
        payload,
        format="json",
    )
    second_response = api_client.post(
        "/api/v1/auth/token/",
        payload,
        format="json",
    )
    third_response = api_client.post(
        "/api/v1/auth/token/",
        payload,
        format="json",
    )

    assert first_response.status_code == 401
    assert second_response.status_code == 401
    assert third_response.status_code == 429
    assert "Retry-After" in third_response.headers


@pytest.mark.django_db
def test_google_oauth_token_endpoint_is_throttled(
    api_client,
    user,
    monkeypatch,
):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {
            **ScopedRateThrottle.THROTTLE_RATES,
            "google_oauth_token": "2/minute",
        },
    )

    api_client.force_login(user)

    first_response = api_client.get(
        "/api/v1/accounts/oauth/google/token/",
    )
    second_response = api_client.get(
        "/api/v1/accounts/oauth/google/token/",
    )
    third_response = api_client.get(
        "/api/v1/accounts/oauth/google/token/",
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 429

    assert "Retry-After" in third_response.headers
    assert third_response.data["success"] is False

    assert "access" in first_response.data
    assert "refresh" in first_response.data
    assert "user" in first_response.data


@pytest.mark.django_db
def test_refresh_token_endpoint_is_throttled(authenticated_client, monkeypatch, user):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {
            **ScopedRateThrottle.THROTTLE_RATES,
            "token_refresh": "2/minute",
        },
    )
    refresh_token = RefreshToken.for_user(user)
    payload = {"refresh": refresh_token}

    first_response = authenticated_client.post("/api/v1/auth/token/refresh/", payload)

    second_response = authenticated_client.post("/api/v1/auth/token/refresh/", payload)

    third_response = authenticated_client.post("/api/v1/auth/token/refresh/", payload)

    assert third_response.status_code == 429
    assert "Retry-After" in third_response.headers
    assert third_response.data["success"] is False

    assert "access" in first_response.data
    assert "access" in second_response.data
