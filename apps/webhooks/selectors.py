from uuid import UUID

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.webhooks.constants import WEBHOOK_RETRY_DELAYS
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEventType


def webhook_endpoint_list_for_user(*, user: User) -> QuerySet[WebhookEndpoint]:
    return WebhookEndpoint.objects.filter(owner=user).order_by("-created_at")


def webhook_endpoint_get_for_user(
    *, user: User, endpoint_id: UUID
) -> WebhookEndpoint | None:
    return WebhookEndpoint.objects.filter(id=endpoint_id, owner=user).first()


def webhook_endpoint_list_active_for_event(
    *, owner: User, event_type: WebhookEventType
) -> QuerySet[WebhookEndpoint]:
    return WebhookEndpoint.objects.filter(
        owner=owner, is_active=True, events__contains=[event_type]
    )


def webhook_delivery_get(*, delivery_id: UUID) -> WebhookDelivery | None:
    return (
        WebhookDelivery.objects.select_related("endpoint")
        .filter(id=delivery_id)
        .first()
    )


def webhook_delivery_get_retry_delay(*, attempt_count: int) -> int | None:
    return WEBHOOK_RETRY_DELAYS.get(attempt_count)
