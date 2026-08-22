import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.services import user_create
from apps.links.models import ShortLink
from apps.links.services import short_link_create


@pytest.fixture
def user(db) -> User:
    return user_create(email="sulav@mail.com", password="strong-password")


@pytest.fixture
def short_link(user) -> ShortLink:
    return short_link_create(
        owner=user,
        destination_url="https://example.com/first",
        short_code="portfolio",
    )


@pytest.fixture
def another_user() -> User:
    return user_create(
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
