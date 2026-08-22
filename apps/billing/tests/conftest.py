from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.services import user_create
from apps.links.models import ShortLink
from apps.links.services import short_link_create


@pytest.fixture
def user() -> User:
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


class FakeStripeObject(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def build_stripe_subscription_event(**overrides):
    defaults = {
        "id": "sub_test123",
        "customer": "cus_test123",
        "status": "active",
        "current_period_start": 1700000000,
        "current_period_end": 1702592000,
        "cancel_at_period_end": False,
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_test123",
                    },
                },
            ],
        },
    }

    defaults.update(overrides)

    return SimpleNamespace(data=SimpleNamespace(object=FakeStripeObject(defaults)))


def build_stripe_invoice_event(**overrides):
    defaults = {
        "id": "in_test123",
        "subscription": "sub_test123",
        "customer": "cus_test123",
    }
    defaults.update(overrides)

    return SimpleNamespace(data=SimpleNamespace(object=FakeStripeObject(defaults)))
