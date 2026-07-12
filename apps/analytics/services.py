from apps.analytics.models import ClickEvent
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
