from django.db.models import QuerySet
from django.utils import timezone

from apps.core.models import IdempotencyRecord


def idempotency_record_list_expired() -> QuerySet[IdempotencyRecord]:
    return IdempotencyRecord.objects.filter(
        expires_at__lte=timezone.now(),
    )
