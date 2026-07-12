import logging
from uuid import UUID

from celery import shared_task
from django.db import DatabaseError

from apps.analytics.services import click_event_create
from apps.links.models import ShortLink

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(DatabaseError,), retry_backoff=True, retry_kwargs={"max_retries": 3}
)
def click_event_create_task(
    *,
    short_link_id: str,
    referrer: str = "",
    user_agent: str = "",
    ip_address: str | None = None,
) -> None:
    try:
        short_link = ShortLink.objects.get(id=UUID(short_link_id))
    except (ShortLink.DoesNotExist, ValueError):
        logger.warning(
            "Click event was not recorded because short link %s no longer exists.",
            short_link_id,
        )
        return

    click_event_create(
        short_link=short_link,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
    )
