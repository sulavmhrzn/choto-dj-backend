from datetime import datetime
from uuid import uuid4

from django.utils import timezone

from apps.webhooks.events import build_webhook_event_payload


def test_build_webhook_event_payload_returns_stable_structure() -> None:
    event_id = uuid4()
    created_at = timezone.make_aware(
        datetime(
            year=2026,
            month=7,
            day=28,
            hour=12,
        )
    )

    payload = build_webhook_event_payload(
        event_id=event_id,
        event_type="short_link.created",
        created_at=created_at,
        data={
            "short_code": "docs",
        },
    )

    assert payload == {
        "id": str(event_id),
        "type": "short_link.created",
        "created_at": created_at.isoformat(),
        "data": {
            "short_code": "docs",
        },
    }
