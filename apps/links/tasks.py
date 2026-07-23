import structlog
from celery import shared_task

from apps.links.services import short_link_deactivate_expired

logger = structlog.getLogger()


@shared_task
def short_link_deactivate_expired_task() -> int:
    updated_count = short_link_deactivate_expired()

    logger.info("expired_short_links_deactivated", updated_count=updated_count)

    return updated_count
