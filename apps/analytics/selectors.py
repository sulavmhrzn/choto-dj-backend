from datetime import datetime

from django.db.models import Count, Max, Min, Q, QuerySet
from django.db.models.functions import TruncDate

from apps.analytics.models import ClickEvent
from apps.analytics.types import ClickEventSummary
from apps.links.models import ShortLink


def click_event_recent_for_link(
    *,
    short_link: ShortLink,
    limit: int = 20,
) -> QuerySet[ClickEvent]:
    return ClickEvent.objects.filter(short_link=short_link).order_by("-clicked_at")[
        :limit
    ]


def click_event_summary_for_link(
    *, short_link: ShortLink, since: datetime
) -> ClickEventSummary:
    result = ClickEvent.objects.filter(
        short_link=short_link,
    ).aggregate(
        total_clicks=Count("id"),
        clicks_since=Count("id", filter=Q(clicked_at__gte=since)),
        unique_visitors=Count("ip_address", distinct=True),
        first_clicked_at=Min("clicked_at"),
        last_clicked_at=Max("clicked_at"),
    )
    return {
        "total_clicks": result["total_clicks"],
        "clicks_since": result["clicks_since"],
        "unique_visitors": result["unique_visitors"],
        "first_clicked_at": result["first_clicked_at"],
        "last_clicked_at": result["last_clicked_at"],
    }


def click_event_get_daily_counts(*, short_link: ShortLink, start_at: datetime):
    return (
        ClickEvent.objects.filter(short_link=short_link, clicked_at__gte=start_at)
        .annotate(date=TruncDate("clicked_at"))
        .values("date")
        .annotate(clicks=Count("id"))
        .order_by("date")
    )
