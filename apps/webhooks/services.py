import secrets
from dataclasses import dataclass

from django.db import transaction

from apps.accounts.models import User
from apps.webhooks.constants import WEBHOOK_SECRET_BYTES, WEBHOOK_SECRET_PREFIX
from apps.webhooks.encryption import encrypt_webhook_secret
from apps.webhooks.models import WebhookEndpoint


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
