import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from apps.webhooks.encryption import decrypt_webhook_secret
from apps.webhooks.models import WebhookEndpoint

WEBHOOK_SIGNATURE_VERSION = "v1"


@dataclass(frozen=True)
class SignedWebhookRequest:
    body: str
    headers: dict[str, str]


def serialize_webhook_payload(
    *,
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def build_webhook_signature(
    *,
    secret: str,
    timestamp: int,
    body: str,
) -> str:
    signed_content = f"{timestamp}.{body}"

    digest = hmac.new(
        secret.encode("utf-8"),
        signed_content.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{WEBHOOK_SIGNATURE_VERSION}={digest}"


def build_signed_webhook_request(
    *,
    endpoint: WebhookEndpoint,
    payload: dict[str, Any],
    timestamp: int,
) -> SignedWebhookRequest:
    body = serialize_webhook_payload(payload=payload)

    secret = decrypt_webhook_secret(encrypted_secret=endpoint.encrypted_secret)

    signature = build_webhook_signature(
        secret=secret,
        timestamp=timestamp,
        body=body,
    )

    return SignedWebhookRequest(
        body=body,
        headers={
            "Content-Type": "application/json",
            "Choto-Event-ID": str(payload["id"]),
            "Choto-Event-Type": str(payload["type"]),
            "Choto-Timestamp": str(timestamp),
            "Choto-Signature": signature,
        },
    )
