import hashlib
import hmac

import pytest
from cryptography.fernet import Fernet

from apps.webhooks.models import WebhookEventType
from apps.webhooks.services import webhook_endpoint_create
from apps.webhooks.signing import (
    build_signed_webhook_request,
    build_webhook_signature,
    serialize_webhook_payload,
)


def test_serialize_webhook_payload_is_stable():
    first = serialize_webhook_payload(
        payload={
            "type": "short_link.created",
            "id": "event-123",
        }
    )
    second = serialize_webhook_payload(
        payload={
            "id": "event-123",
            "type": "short_link.created",
        }
    )

    assert first == second


def test_build_webhook_signature_uses_timestamp_and_body():
    secret = "whsec_test"
    timestamp = 1785400000
    body = '{"id":"event-123"}'

    signature = build_webhook_signature(
        secret=secret,
        timestamp=timestamp,
        body=body,
    )

    expected_digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert signature == f"v1={expected_digest}"


@pytest.mark.django_db
def test_build_signed_webhook_request_returns_body_and_headers(settings, user):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    )

    payload = {
        "id": "event-123",
        "type": WebhookEventType.SHORT_LINK_CREATED,
        "created_at": "2026-07-30T12:00:00+00:00",
        "data": {
            "short_code": "docs",
        },
    }

    signed_request = build_signed_webhook_request(
        endpoint=created.endpoint,
        payload=payload,
        timestamp=1785400000,
    )

    assert signed_request.body == (
        '{"created_at":"2026-07-30T12:00:00+00:00",'
        '"data":{"short_code":"docs"},'
        '"id":"event-123",'
        '"type":"short_link.created"}'
    )
    assert signed_request.headers["Content-Type"] == "application/json"
    assert signed_request.headers["Choto-Event-ID"] == "event-123"
    assert signed_request.headers["Choto-Event-Type"] == (
        WebhookEventType.SHORT_LINK_CREATED
    )
    assert signed_request.headers["Choto-Timestamp"] == "1785400000"
    assert signed_request.headers["Choto-Signature"].startswith("v1=")
