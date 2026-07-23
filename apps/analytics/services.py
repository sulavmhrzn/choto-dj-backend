from datetime import date, timedelta

from apps.analytics.models import ClickEvent
from apps.analytics.types import DailyClickCount
from apps.links.models import ShortLink


def click_event_create(
    *,
    short_link: ShortLink,
    referrer: str = "",
    user_agent: str = "",
    ip_address: str | None = None,
) -> ClickEvent:
    return ClickEvent.objects.create(
        short_link=short_link,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
    )


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
