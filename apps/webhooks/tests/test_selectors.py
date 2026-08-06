import pytest
from cryptography.fernet import Fernet

from apps.accounts.models import User
from apps.webhooks.models import WebhookEventType
from apps.webhooks.selectors import webhook_endpoint_list_active_for_event
from apps.webhooks.services import webhook_endpoint_create


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@mail.com",
        password="sulavmhrzn",
    )


@pytest.mark.django_db
def test_webhook_endpoint_list_active_for_event_returns_subscribed_endpoints(
    settings,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    subscribed = webhook_endpoint_create(
        owner=user,
        name="Subscribed",
        url="https://example.com/subscribed/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    ).endpoint

    webhook_endpoint_create(
        owner=user,
        name="Different event",
        url="https://example.com/different/",
        events=[
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    )

    disabled = webhook_endpoint_create(
        owner=user,
        name="Disabled",
        url="https://example.com/disabled/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    ).endpoint

    disabled.is_active = False
    disabled.save(
        update_fields=[
            "is_active",
        ]
    )

    results = list(
        webhook_endpoint_list_active_for_event(
            owner=user,
            event_type=WebhookEventType.SHORT_LINK_CREATED,
        )
    )

    assert results == [
        subscribed,
    ]
