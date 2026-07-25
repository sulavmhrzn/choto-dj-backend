import structlog
from celery import shared_task

from apps.core.services import idempotency_record_delete_expired

logger = structlog.getLogger()


@shared_task
def idempotency_record_delete_expired_task() -> int:
    deleted_count = idempotency_record_delete_expired()

    logger.info("expired_idempotency_records_deleted", deleted_count=deleted_count)

    return deleted_count
