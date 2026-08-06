import math
from uuid import UUID

import structlog
from celery import shared_task
from django.utils import timezone

from apps.webhooks.models import WebhookDeliveryStatus

logger = structlog.getLogger()


@shared_task
def webhook_delivery_send_task(
    *,
    delivery_id: str,
):
    from apps.webhooks.metrics import webhook_delivery_retries_total
    from apps.webhooks.services import webhook_delivery_send

    delivery = webhook_delivery_send(delivery_id=UUID(delivery_id))

    if delivery is None:
        logger.warning(
            "webhook_delivery_not_found",
            delivery_id=delivery_id,
        )
        return

    logger.info(
        "webhook_delivery_attempted",
        delivery_id=str(delivery.id),
        event_id=str(delivery.event_id),
        status=delivery.status,
        response_status=delivery.response_status,
        attempt_count=delivery.attempt_count,
    )

    if (
        delivery.status != WebhookDeliveryStatus.FAILED
        or delivery.next_attempt_at is None
    ):
        return

    retry_delay = max(
        0,
        math.ceil(
            (delivery.next_attempt_at - timezone.now()).total_seconds(),
        ),
    )

    webhook_delivery_send_task.apply_async(
        kwargs={
            "delivery_id": str(delivery.id),
        },
        countdown=retry_delay,
    )
    webhook_delivery_retries_total.inc()

    logger.info(
        "webhook_delivery_retry_scheduled",
        delivery_id=str(delivery.id),
        event_id=str(delivery.event_id),
        attempt_count=delivery.attempt_count,
        retry_delay=retry_delay,
        next_attempt_at=delivery.next_attempt_at,
    )
