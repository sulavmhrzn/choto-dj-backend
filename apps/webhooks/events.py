from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID


class WebhookEventPayload(TypedDict):
    id: str
    type: str
    created_at: str
    data: dict[str, Any]


def build_webhook_event_payload(
    *,
    event_id: UUID,
    event_type: str,
    created_at: datetime,
    data: dict[str, Any],
) -> WebhookEventPayload:
    return {
        "id": str(event_id),
        "type": event_type,
        "created_at": created_at.isoformat(),
        "data": data,
    }
