import hashlib
import json
from datetime import date, datetime
from typing import Any

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
IDEMPOTENCY_KEY_MAX_LENGTH = 255


def _serialize_idempotency_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return value


def build_idempotency_request_hash(*, data: dict) -> str:
    normalized_data = {
        key: _serialize_idempotency_value(value) for key, value in data.items()
    }

    serialized_data = json.dumps(
        normalized_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(serialized_data.encode("utf-8")).hexdigest()


def get_idempotency_key(*, request: Request) -> str | None:
    value = request.headers.get(IDEMPOTENCY_KEY_HEADER)
    if value is None:
        return None

    value = value.strip()

    if not value:
        raise ValidationError(
            {
                "idempotency_key": ["Idempotency-Key cannot be blank."],
            }
        )

    if len(value) > IDEMPOTENCY_KEY_MAX_LENGTH:
        raise ValidationError(
            {
                "idempotency_key": [
                    f"Idempotency-Key cannot exceed {IDEMPOTENCY_KEY_MAX_LENGTH} characters."
                ]
            }
        )

    return value
