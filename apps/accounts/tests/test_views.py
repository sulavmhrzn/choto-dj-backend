import hashlib
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import APIKey, User

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
def another_user() -> User:
    return User.objects.create_user(
        email="sweta@example.com",
        password="strong-password",
        full_name="Sweta Maharjan",
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


@pytest.mark.django_db
def test_api_key_create_returns_secret_once(authenticated_client, user):
    response = authenticated_client.post(
        reverse("accounts:api-key-list-create"),
        data={"name": "Github Actions"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert response.data["name"] == "Github Actions"
    assert response.data["is_active"] is True
    assert response.data["last_used_at"] is None
    assert response.data["revoked_at"] is None

    complete_key = response.data["key"]

    assert complete_key.startswith(f"choto_{response.data['prefix']}.")

    api_key = APIKey.objects.get(id=response.data["id"])

    assert api_key.owner == user
    assert api_key.name == "Github Actions"
    assert api_key.prefix == response.data["prefix"]


@pytest.mark.django_db
def test_api_key_create_stores_only_secret_hash(
    authenticated_client,
) -> None:
    response = authenticated_client.post(
        reverse("accounts:api-key-list-create"),
        data={
            "name": "Personal CLI",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    complete_key = response.data["key"]

    _, secret = complete_key.split(".", maxsplit=1)

    api_key = APIKey.objects.get(
        id=response.data["id"],
    )

    expected_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()

    assert api_key.hashed_secret == expected_hash
    assert api_key.hashed_secret != secret
    assert complete_key != api_key.hashed_secret


@pytest.mark.django_db
def test_api_key_create_requires_authentication(
    api_client: APIClient,
) -> None:
    response = api_client.post(
        reverse("accounts:api-key-list-create"),
        data={
            "name": "Unauthorized key",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert APIKey.objects.count() == 0


@pytest.mark.django_db
def test_api_key_create_rejects_blank_name(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        reverse("accounts:api-key-list-create"),
        data={
            "name": "   ",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert APIKey.objects.count() == 0


@pytest.mark.django_db
def test_api_key_list_returns_only_authenticated_users_keys(
    authenticated_client, user, another_user
):
    APIKey.objects.create(
        owner=user,
        name="Github Actions",
        prefix="github123456",
        hashed_secret="hashed-secret-1",
    )
    APIKey.objects.create(
        owner=user,
        name="Personal CLI",
        prefix="personal1234",
        hashed_secret="hashed-secret-2",
    )
    APIKey.objects.create(
        owner=another_user,
        name="Other user keys",
        prefix="otheruser123",
        hashed_secret="hashed-secret-3",
    )

    response = authenticated_client.get(
        reverse("accounts:api-key-list-create"),
    )

    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 2
    assert {item["name"] for item in response.data} == {
        "Github Actions",
        "Personal CLI",
    }


@pytest.mark.django_db
def test_api_key_list_does_not_expose_secrets(
    authenticated_client,
    user,
) -> None:
    APIKey.objects.create(
        owner=user,
        name="Deployment",
        prefix="deployment12",
        hashed_secret="very-sensitive-hash",
    )

    response = authenticated_client.get(
        reverse("accounts:api-key-list-create"),
    )

    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 1

    api_key_data = response.data[0]

    assert "key" not in api_key_data
    assert "secret" not in api_key_data
    assert "hashed_secret" not in api_key_data


@pytest.mark.django_db
def test_api_key_list_returns_empty_list_when_user_has_no_keys(
    authenticated_client,
) -> None:
    response = authenticated_client.get(
        reverse("accounts:api-key-list-create"),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.django_db
def test_api_key_list_requires_authentication(
    api_client,
) -> None:
    response = api_client.get(
        reverse("accounts:api-key-list-create"),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_api_key_revoke_endpoint_revokes_owned_key(authenticated_client, user):
    api_key = APIKey.objects.create(
        owner=user,
        name="Deployment",
        prefix="deployment123",
        hashed_secret="hashed-secret",
    )

    response = authenticated_client.post(
        reverse("accounts:api-key-revoke", kwargs={"api_key_id": api_key.id})
    )

    assert response.status_code == status.HTTP_200_OK

    assert response.data["id"] == str(api_key.id)
    assert response.data["is_active"] is False
    assert response.data["revoked_at"] is not None

    api_key.refresh_from_db()

    assert api_key.is_active is False
    assert api_key.revoked_at is not None


@pytest.mark.django_db
def test_api_key_revoke_endpoint_does_not_allow_other_users_key(
    authenticated_client: APIClient, another_user
) -> None:

    api_key = APIKey.objects.create(
        owner=another_user,
        name="Other user key",
        prefix="otheruser123",
        hashed_secret="hashed-secret",
    )

    response = authenticated_client.post(
        reverse(
            "accounts:api-key-revoke",
            kwargs={
                "api_key_id": api_key.id,
            },
        )
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    api_key.refresh_from_db()

    assert api_key.is_active is True
    assert api_key.revoked_at is None


@pytest.mark.django_db
def test_api_key_revoke_endpoint_returns_not_found_for_missing_key(
    authenticated_client: APIClient,
) -> None:

    response = authenticated_client.post(
        reverse(
            "accounts:api-key-revoke",
            kwargs={
                "api_key_id": uuid4(),
            },
        )
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_api_key_revoke_endpoint_requires_authentication(
    api_client: APIClient,
    user: User,
) -> None:
    api_key = APIKey.objects.create(
        owner=user,
        name="GitHub Actions",
        prefix="github654321",
        hashed_secret="hashed-secret",
    )

    response = api_client.post(
        reverse(
            "accounts:api-key-revoke",
            kwargs={
                "api_key_id": api_key.id,
            },
        )
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    api_key.refresh_from_db()

    assert api_key.is_active is True


@pytest.mark.django_db
def test_api_key_revoke_endpoint_is_idempotent(
    authenticated_client: APIClient,
    user: User,
) -> None:
    api_key = APIKey.objects.create(
        owner=user,
        name="Personal CLI",
        prefix="personal5678",
        hashed_secret="hashed-secret",
    )

    url = reverse(
        "accounts:api-key-revoke",
        kwargs={
            "api_key_id": api_key.id,
        },
    )

    first_response = authenticated_client.post(url)

    api_key.refresh_from_db()
    original_revoked_at = api_key.revoked_at

    second_response = authenticated_client.post(url)

    api_key.refresh_from_db()

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert api_key.revoked_at == original_revoked_at
