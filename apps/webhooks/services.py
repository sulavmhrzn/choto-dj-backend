import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.webhooks.constants import (
    WEBHOOK_DELIVERY_TIMEOUT_SECONDS,
    WEBHOOK_MAX_DELIVERY_ATTEMPTS,
    WEBHOOK_RESPONSE_BODY_MAX_LENGTH,
    WEBHOOK_SECRET_BYTES,
    WEBHOOK_SECRET_PREFIX,
)
from apps.webhooks.encryption import encrypt_webhook_secret
from apps.webhooks.events import build_webhook_event_payload
from apps.webhooks.metrics import (
    webhook_delivery_attempts_total,
    webhook_delivery_outcomes_total,
)
from apps.webhooks.models import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEventType,
)
from apps.webhooks.selectors import (
    webhook_delivery_get,
    webhook_delivery_get_retry_delay,
    webhook_endpoint_list_active_for_event,
)
from apps.webhooks.signing import build_signed_webhook_request
from apps.webhooks.tasks import webhook_delivery_send_task


@dataclass(frozen=True)
class CreateWebhookEndpoint:
    endpoint: WebhookEndpoint
    secret: str


def generate_webhook_secret() -> str:
    return WEBHOOK_SECRET_PREFIX + secrets.token_urlsafe(WEBHOOK_SECRET_BYTES)


@transaction.atomic
def webhook_endpoint_create(
    *,
    owner: User,
    name: str,
    url: str,
    events: list[str],
) -> CreateWebhookEndpoint:
    secret = generate_webhook_secret()
    endpoint = WebhookEndpoint.objects.create(
        owner=owner,
        name=name,
        url=url,
        events=events,
        encrypted_secret=encrypt_webhook_secret(secret=secret),
    )

    return CreateWebhookEndpoint(endpoint=endpoint, secret=secret)


@transaction.atomic
def webhook_endpoint_update(
    *,
    endpoint: WebhookEndpoint,
    name: str | None = None,
    url: str | None = None,
    events: list[str] | None = None,
    is_active: bool | None = None,
) -> WebhookEndpoint:
    update_fields: list[str] = []

    if name is not None and endpoint.name != name:
        endpoint.name = name
        update_fields.append("name")

    if url is not None and endpoint.url != url:
        endpoint.url = url
        update_fields.append("url")

    if events is not None and endpoint.events != events:
        endpoint.events = events
        update_fields.append("events")

    if is_active is not None and endpoint.is_active != is_active:
        endpoint.is_active = is_active
        update_fields.append("is_active")

    if not update_fields:
        return endpoint

    update_fields.append("updated_at")
    endpoint.save(update_fields=update_fields)
    return endpoint


@transaction.atomic
def webhook_deliveries_create_for_event(
    *,
    owner: User,
    event_type: WebhookEventType,
    data: dict[str, Any],
    created_at: datetime | None = None,
) -> list[WebhookDelivery]:
    event_id = uuid4()
    event_created_at = created_at or timezone.now()

    payload = build_webhook_event_payload(
        event_id=event_id,
        event_type=event_type,
        created_at=event_created_at,
        data=data,
    )

    endpoints = list(
        webhook_endpoint_list_active_for_event(
            owner=owner,
            event_type=event_type,
        )
    )

    if not endpoints:
        return []

    deliveries = [
        WebhookDelivery(
            endpoint=endpoint,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        for endpoint in endpoints
    ]
    return WebhookDelivery.objects.bulk_create(deliveries)


def webhook_deliveries_dispatch(*, deliveries: list[WebhookDelivery]) -> None:
    delivery_ids = [delivery.id for delivery in deliveries]

    if not delivery_ids:
        return

    transaction.on_commit(
        lambda delivery_ids=delivery_ids: [
            webhook_delivery_send_task.delay(
                delivery_id=str(delivery_id),
            )
            for delivery_id in delivery_ids
        ]
    )


def webhook_event_dispatch(
    *,
    owner: User,
    event_type: WebhookEventType,
    data: dict[str, Any],
    created_at: datetime | None = None,
) -> list[WebhookDelivery]:
    deliveries = webhook_deliveries_create_for_event(
        owner=owner,
        event_type=event_type,
        data=data,
        created_at=created_at,
    )

    webhook_deliveries_dispatch(deliveries=deliveries)

    return deliveries


def webhook_delivery_should_retry(
    *, response_status: int | None, attempt_count: int
) -> bool:
    if attempt_count >= WEBHOOK_MAX_DELIVERY_ATTEMPTS:
        return False

    if response_status is None:
        return True

    return response_status in {408, 429} or 500 <= response_status < 600


def webhook_delivery_send(*, delivery_id: UUID) -> WebhookDelivery | None:
    delivery = webhook_delivery_get(delivery_id=delivery_id)

    if delivery is None:
        return None

    if delivery.status == WebhookDeliveryStatus.SUCCEEDED:
        return delivery

    if not delivery.endpoint.is_active:
        delivery.status = WebhookDeliveryStatus.FAILED
        delivery.error_message = "Webhook endpoint is inactive."
        delivery.next_attempt_at = None

        delivery.save(
            update_fields=[
                "status",
                "error_message",
                "next_attempt_at",
                "updated_at",
            ]
        )

        return delivery

    delivery.status = WebhookDeliveryStatus.PROCESSING
    delivery.attempt_count += 1
    delivery.error_message = ""
    delivery.next_attempt_at = None

    delivery.save(
        update_fields=[
            "status",
            "attempt_count",
            "error_message",
            "next_attempt_at",
            "updated_at",
        ]
    )

    timestamp = int(timezone.now().timestamp())
    webhook_delivery_attempts_total.inc()

    try:
        signed_request = build_signed_webhook_request(
            endpoint=delivery.endpoint,
            payload=delivery.payload,
            timestamp=timestamp,
        )

        response = httpx.post(
            url=delivery.endpoint.url,
            content=signed_request.body,
            headers=signed_request.headers,
            timeout=WEBHOOK_DELIVERY_TIMEOUT_SECONDS,
        )

    except httpx.HTTPError as exc:
        webhook_delivery_outcomes_total.labels(outcomes="failure").inc()

        delivery.status = WebhookDeliveryStatus.FAILED
        delivery.response_status = None
        delivery.response_body = ""
        delivery.error_message = str(exc)[:WEBHOOK_RESPONSE_BODY_MAX_LENGTH]

        if webhook_delivery_should_retry(
            response_status=None, attempt_count=delivery.attempt_count
        ):
            retry_delay = webhook_delivery_get_retry_delay(
                attempt_count=delivery.attempt_count
            )

            delivery.next_attempt_at = (
                timezone.now() + timedelta(seconds=retry_delay)
                if retry_delay is not None
                else None
            )
        else:
            delivery.next_attempt_at = None

        delivery.save(
            update_fields=[
                "status",
                "response_status",
                "response_body",
                "error_message",
                "delivered_at",
                "next_attempt_at",
                "updated_at",
            ]
        )

        return delivery

    delivery.response_status = response.status_code
    delivery.response_body = response.text[:WEBHOOK_RESPONSE_BODY_MAX_LENGTH]
    delivery.error_message = ""

    if 200 <= response.status_code < 300:
        delivery.status = WebhookDeliveryStatus.SUCCEEDED
        delivery.delivered_at = timezone.now()
        delivery.next_attempt_at = None

        webhook_delivery_outcomes_total.labels(outcomes="success").inc()
    else:
        delivery.status = WebhookDeliveryStatus.FAILED
        delivery.delivered_at = None

        webhook_delivery_outcomes_total.labels(outcomes="failure").inc()

        if webhook_delivery_should_retry(
            response_status=response.status_code, attempt_count=delivery.attempt_count
        ):
            retry_delay = webhook_delivery_get_retry_delay(
                attempt_count=delivery.attempt_count
            )

            delivery.next_attempt_at = (
                timezone.now() + timedelta(seconds=retry_delay)
                if retry_delay is not None
                else None
            )
        else:
            delivery.next_attempt_at = None

    delivery.save(
        update_fields=[
            "status",
            "response_status",
            "response_body",
            "error_message",
            "delivered_at",
            "next_attempt_at",
            "updated_at",
        ]
    )

    return delivery
