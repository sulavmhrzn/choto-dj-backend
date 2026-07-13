from datetime import datetime

from django.core.cache import cache
from django.utils import timezone

from config import settings


def short_link_redirect_cache_key(*, short_code: str) -> str:
    return f"short-link:redirect:{short_code.lower()}"


def short_link_redirect_cache_delete(*, short_code: str) -> None:
    cache.delete(
        short_link_redirect_cache_key(short_code=short_code),
    )


def get_redirect_cache_timeout(*, expires_at: datetime | None) -> int:
    default_timeout = settings.SHORT_LINK_CACHE_TIMEOUT

    if expires_at is None:
        return default_timeout

    seconds_until_expiration = int((expires_at - timezone.now()).total_seconds())
    return max(1, min(default_timeout, seconds_until_expiration))
