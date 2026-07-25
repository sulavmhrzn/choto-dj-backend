from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import IdempotencyRecord
from apps.core.selectors import idempotency_record_list_expired
from apps.links.models import ShortLink

IDEMPOTENCY_RECORD_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    created: bool


@transaction.atomic
def idempotency_record_claim(
    *, owner: User, key: str, request_hash: str
) -> IdempotencyClaim:
    now = timezone.now()

    existing_record = (
        IdempotencyRecord.objects.select_for_update()
        .filter(owner=owner, key=key)
        .first()
    )

    if existing_record is not None:
        if existing_record.expires_at > now:
            return IdempotencyClaim(
                record=existing_record,
                created=False,
            )
        existing_record.delete()

    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                owner=owner,
                key=key,
                request_hash=request_hash,
                expires_at=now + IDEMPOTENCY_RECORD_TTL,
            )
    except IntegrityError:
        record = IdempotencyRecord.objects.select_for_update().get(owner=owner, key=key)
        return IdempotencyClaim(record=record, created=False)

    return IdempotencyClaim(record=record, created=True)


@transaction.atomic
def idempotency_record_complete(
    *,
    record: IdempotencyRecord,
    response_status: int,
    response_data: dict[str, Any],
    short_link: ShortLink,
) -> IdempotencyRecord:
    if record.status == IdempotencyRecord.Status.COMPLETED:
        return record

    record.status = IdempotencyRecord.Status.COMPLETED
    record.response_data = response_data
    record.response_status = response_status
    record.short_link = short_link

    record.save(
        update_fields=[
            "status",
            "response_status",
            "response_data",
            "short_link",
        ]
    )

    return record


@transaction.atomic
def idempotency_record_delete_expired() -> int:
    deleted_count, _ = idempotency_record_list_expired().delete()
    return deleted_count
