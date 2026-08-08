import pytest
from cryptography.fernet import Fernet

from apps.accounts.models import User
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEventType
from apps.webhooks.services import webhook_endpoint_create


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@mail.com",
        password="sulavmhrzn",
    )


@pytest.fixture
def another_user() -> User:
    return User.objects.create_user(
        email="sweta@mail.com",
        password="sweta",
    )


@pytest.fixture
def webhook_endpoint(
    settings,
    user,
) -> WebhookEndpoint:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    return webhook_endpoint_create(
        owner=user,
        name="Test endpoint",
        url="https://example.com/webhooks/choto/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    ).endpoint


@pytest.fixture
def webhook_delivery(
    webhook_endpoint,
) -> WebhookDelivery:
    return WebhookDelivery.objects.create(
        endpoint=webhook_endpoint,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        payload={
            "id": "f84f8dd5-29bb-479c-a979-314871c87949",
            "type": WebhookEventType.SHORT_LINK_CREATED,
            "created_at": "2026-07-29T08:00:00+00:00",
            "data": {
                "short_link_id": "cc8680ce-b3ba-49fb-a982-45687466ca19",
                "short_code": "docs",
                "destination_url": "https://example.com/docs",
            },
        },
    )
