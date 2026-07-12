import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import User


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@example.com",
        password="strong-password",
        full_name="Sulav Maharjan",
    )


@pytest.mark.django_db
def test_token_obtain_returns_tokens_and_user(
    api_client: APIClient,
    user: User,
) -> None:
    response = api_client.post(
        reverse("token_obtain_pair"),
        data={
            "email": user.email,
            "password": "strong-password",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data

    assert response.data["user"]["id"] == str(user.id)
    assert response.data["user"]["email"] == user.email
    assert response.data["user"]["full_name"] == user.full_name

    access = AccessToken(response.data["access"])
    refresh = RefreshToken(response.data["refresh"])

    assert str(access["user_id"]) == str(user.id)
    assert str(refresh["user_id"]) == str(user.id)


@pytest.mark.django_db
def test_token_obtain_rejects_invalid_password(
    api_client: APIClient,
    user: User,
) -> None:
    response = api_client.post(
        reverse("token_obtain_pair"),
        data={
            "email": user.email,
            "password": "wrong-password",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.data


@pytest.mark.django_db
def test_token_obtain_rejects_unknown_email(
    api_client: APIClient,
) -> None:
    response = api_client.post(
        reverse("token_obtain_pair"),
        data={
            "email": "missing@example.com",
            "password": "strong-password",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_token_obtain_rejects_inactive_user(
    api_client: APIClient,
    user: User,
) -> None:
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = api_client.post(
        reverse("token_obtain_pair"),
        data={
            "email": user.email,
            "password": "strong-password",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_token_refresh_returns_new_access_tokens(
    api_client: APIClient,
    user: User,
) -> None:
    refresh = RefreshToken.for_user(user)

    response = api_client.post(
        reverse("token_refresh"),
        data={"refresh": str(refresh)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data

    access = AccessToken(response.data["access"])

    assert str(access["user_id"]) == str(user.id)


@pytest.mark.django_db
def test_token_verify_accepts_valid_access_token(
    api_client: APIClient,
    user: User,
) -> None:
    refresh = RefreshToken.for_user(user)

    response = api_client.post(
        reverse("token_verify"),
        data={"token": str(refresh.access_token)},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {}


@pytest.mark.django_db
def test_token_verify_rejects_invalid_token(
    api_client: APIClient,
) -> None:
    response = api_client.post(
        reverse("token_verify"),
        data={"token": "invalid-token"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
