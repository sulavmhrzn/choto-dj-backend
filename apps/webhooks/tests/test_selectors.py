import json
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEventType
from apps.webhooks.selectors import (
    webhook_delivery_get_for_user,
    webhook_delivery_list_for_endpoint,
    webhook_endpoint_count_for_user,
    webhook_endpoint_list_active_for_event,
)
from apps.webhooks.services import (
    webhook_endpoint_create,
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


@pytest.mark.django_db
def test_webhook_delivery_list_for_endpoint_returns_owned_deliveries(
    user, webhook_endpoint
):
    first_delivery = WebhookDelivery.objects.create(
        endpoint=webhook_endpoint,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        payload=json.dumps(
            {"event": "short_link.created"},
        ),
    )
    first_delivery.created_at = timezone.now() - timedelta(days=1)
    first_delivery.save(update_fields=["created_at"])

    second_delivery = WebhookDelivery.objects.create(
        endpoint=webhook_endpoint,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        payload=json.dumps(
            {"event": "short_link.created"},
        ),
    )
    deliveries = list(
        webhook_delivery_list_for_endpoint(user=user, endpoint_id=webhook_endpoint.id)
    )
    assert deliveries == [second_delivery, first_delivery]


@pytest.mark.django_db
def test_webhook_delivery_list_for_endpoint_excludes_other_users_deliveries(
    user, another_user, webhook_delivery
):
    deliveries = list(
        webhook_delivery_list_for_endpoint(
            user=another_user, endpoint_id=webhook_delivery.endpoint.id
        )
    )

    assert deliveries == []


@pytest.mark.django_db
def test_webhook_delivery_list_for_endpoint_excludes_other_endpoints(user):
    requested_endpoint = webhook_endpoint_create(
        owner=user,
        name="Requested endpoint",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    ).endpoint

    other_endpoint = webhook_endpoint_create(
        owner=user,
        name="Other endpoint",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    ).endpoint

    expected_delivery = WebhookDelivery.objects.create(
        endpoint=requested_endpoint,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        payload=json.dumps(
            {"event": "short_link.created"},
        ),
    )
    WebhookDelivery.objects.create(
        endpoint=other_endpoint,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        payload=json.dumps(
            {"event": "short_link.created"},
        ),
    )

    deliveries = list(
        webhook_delivery_list_for_endpoint(user=user, endpoint_id=requested_endpoint.id)
    )

    assert deliveries == [expected_delivery]


@pytest.mark.django_db
def test_webhook_delivery_get_for_user_returns_owned_delivery(user, webhook_delivery):
    result = webhook_delivery_get_for_user(user=user, delivery_id=webhook_delivery.id)

    assert result == webhook_delivery


@pytest.mark.django_db
def test_webhook_delivery_get_for_user_returns_none_for_another_user(
    user, another_user, webhook_delivery
):
    result = webhook_delivery_get_for_user(
        user=another_user, delivery_id=webhook_delivery.id
    )

    assert result is None


@pytest.mark.django_db
def test_webhook_delivery_get_for_user_returns_none_when_missing(
    user,
):
    result = webhook_delivery_get_for_user(
        user=user,
        delivery_id=uuid4(),
    )

    assert result is None


@pytest.mark.django_db
def test_webhook_endpoint_count_for_user_includes_inactive(user):
    WebhookEndpoint.objects.create(
        owner=user,
        name="active",
        url="https://a.com",
        events=[],
        is_active=True,
    )
    WebhookEndpoint.objects.create(
        owner=user,
        name="inactive",
        url="https://b.com",
        events=[],
        is_active=False,
    )

    assert webhook_endpoint_count_for_user(user=user) == 2
