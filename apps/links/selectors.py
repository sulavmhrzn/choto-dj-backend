from uuid import UUID

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.links.models import ShortLink


def short_link_list_for_user(*, user: User) -> QuerySet[ShortLink]:
    return ShortLink.objects.filter(owner=user)


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


def short_link_get_redirectable_by_code(*, short_code: str) -> ShortLink | None:
    now = timezone.now()

    return (
        ShortLink.objects.filter(short_code=short_code, is_active=True)
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        .first()
    )
