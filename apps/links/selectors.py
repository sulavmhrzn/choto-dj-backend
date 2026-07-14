from datetime import datetime
from typing import Literal
from uuid import UUID

from django.core.cache import cache
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.links.cache import get_redirect_cache_timeout, short_link_redirect_cache_key
from apps.links.models import ShortLink
from apps.links.types import RedirectableShortLink

_CACHE_MISS = "__missing__"

ShortLinkOrdering = Literal[
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
    "title",
    "-title",
]


def short_link_list_for_user(
    *,
    user: User,
    is_active: bool | None = None,
    search: str = "",
    ordering: ShortLinkOrdering = "-created_at",
) -> QuerySet[ShortLink]:
    queryset = ShortLink.objects.filter(owner=user)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(short_code__icontains=search)
            | Q(destination_url__icontains=search)
        )
    return queryset.order_by(ordering)


def short_link_get_for_user(*, user: User, link_id: UUID | str) -> ShortLink | None:
    try:
        return ShortLink.objects.get(id=link_id, owner=user)
    except ShortLink.DoesNotExist:
        return None


def short_link_get_by_code(*, short_code: str) -> ShortLink | None:
    try:
        return ShortLink.objects.get(short_code=short_code)
    except ShortLink.DoesNotExist:
        return None


def _short_link_get_redirectable_from_db(
    *, short_code: str
) -> RedirectableShortLink | None:
    now = timezone.now()
    link = (
        ShortLink.objects.filter(short_code=short_code, is_active=True)
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        .values("id", "destination_url", "expires_at")
        .first()
    )

    if link is None:
        return None

    return RedirectableShortLink(
        id=link["id"],
        destination_url=link["destination_url"],
        expires_at=link["expires_at"],
    )


def short_link_get_redirectable_by_code(
    *, short_code: str
) -> RedirectableShortLink | None:
    cache_key = short_link_redirect_cache_key(short_code=short_code)

    cached_data = cache.get(cache_key)

    if cached_data == _CACHE_MISS:
        return None

    if isinstance(cached_data, dict):
        expires_at_value: str | None = cached_data.get("expires_at")

        expires_at = (
            datetime.fromisoformat(expires_at_value) if expires_at_value else None
        )

        if expires_at is not None and expires_at <= timezone.now():
            cache.delete(cache_key)
            return None

        return RedirectableShortLink(
            id=UUID(cached_data["id"]),
            destination_url=cached_data["destination_url"],
            expires_at=expires_at,
        )

    link = _short_link_get_redirectable_from_db(short_code=short_code)

    if link is None:
        cache.set(cache_key, _CACHE_MISS, timeout=30)
        return None

    timeout = get_redirect_cache_timeout(expires_at=link.expires_at)

    cache.set(
        cache_key,
        {
            "id": str(link.id),
            "destination_url": link.destination_url,
            "expires_at": (link.expires_at.isoformat() if link.expires_at else None),
        },
        timeout=timeout,
    )
    return link
