from datetime import datetime

from django.db.models import Count, Q, QuerySet

from apps.analytics.models import ClickEvent
from apps.links.models import ShortLink


def click_event_list_for_link(*, short_link: ShortLink) -> QuerySet[ClickEvent]:
    return ClickEvent.objects.filter(short_link=short_link)


def click_event_recent_for_link(
    *,
    short_link: ShortLink,
    limit: int = 20,
) -> QuerySet[ClickEvent]:
    return ClickEvent.objects.filter(short_link=short_link).order_by("-clicked_at")


def click_event_count_for_link(*, short_link: ShortLink) -> int:
    return ClickEvent.objects.filter(short_link=short_link).count()


def click_event_count_for_link_since(*, short_link: ShortLink, since: datetime) -> int:
    return ClickEvent.objects.filter(
        short_link=short_link, clicked_at__gte=since
    ).count()


def click_event_summary_for_link(
    *, short_link: ShortLink, since: datetime
) -> dict[str, int]:
    result = ClickEvent.objects.filter(
        short_link=short_link,
    ).aggregate(
        total_clicks=Count("id"),
        clicks_since=Count("id", filter=Q(clicked_at__gte=since)),
    )
    return {
        "total_clicks": result["total_clicks"],
        "clicks_since": result["clicks_since"],
    }
