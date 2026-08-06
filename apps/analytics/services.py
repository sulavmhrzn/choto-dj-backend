from datetime import date, timedelta

import structlog
from django.db import transaction

from apps.analytics.models import ClickEvent
from apps.analytics.types import DailyClickCount
from apps.links.models import ShortLink
from apps.webhooks.models import WebhookEventType
from apps.webhooks.services import webhook_event_dispatch

logger = structlog.getLogger()


@transaction.atomic
def click_event_create(
    *,
    short_link: ShortLink,
    referrer: str = "",
    user_agent: str = "",
    ip_address: str | None = None,
) -> ClickEvent:
    click_event = ClickEvent.objects.create(
        short_link=short_link,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    transaction.on_commit(
        lambda click_event=click_event: _handle_short_link_clicked(
            click_event=click_event
        )
    )
    return click_event


def build_daily_click_counts(
    *, start_date: date, end_date: date, counts: list[DailyClickCount]
) -> list[DailyClickCount]:
    counts_by_date = {item["date"]: item["clicks"] for item in counts}
    print("counts_by_date", counts_by_date)
    results: list[DailyClickCount] = []
    current_date = start_date

    while current_date <= end_date:
        results.append(
            {
                "date": current_date,
                "clicks": counts_by_date.get(current_date, 0),
            }
        )
        current_date += timedelta(days=1)
    return results


def _build_short_link_clicked_webhook_data(
    *, click_event: ClickEvent
) -> dict[str, object]:
    short_link = click_event.short_link

    return {
        "click_event_id": str(click_event.id),
        "short_link_id": str(short_link.id),
        "short_code": short_link.short_code,
        "clicked_at": click_event.clicked_at.isoformat(),
        "referrer": click_event.referrer,
        "user_agent": click_event.user_agent,
    }


def _handle_short_link_clicked(*, click_event: ClickEvent):
    try:
        webhook_event_dispatch(
            owner=click_event.short_link.owner,
            event_type=WebhookEventType.SHORT_LINK_CLICKED,
            data=_build_short_link_clicked_webhook_data(click_event=click_event),
            created_at=click_event.clicked_at,
        )
    except Exception:
        logger.exception(
            "short_link_clicked_webhook_dispatch_failed",
            click_event_id=str(click_event.id),
            short_link_id=str(click_event.short_link.id),
        )
