from uuid import UUID

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.webhooks.models import WebhookEndpoint


def webhook_endpoint_list_for_user(*, user: User) -> QuerySet[WebhookEndpoint]:
    return WebhookEndpoint.objects.filter(owner=user).order_by("-created_at")


def webhook_endpoint_get_for_user(
    *, user: User, endpoint_id: UUID
) -> WebhookEndpoint | None:
    return WebhookEndpoint.objects.filter(id=endpoint_id, owner=user).first()
