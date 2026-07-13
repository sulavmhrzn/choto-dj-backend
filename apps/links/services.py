import secrets
import string
from datetime import datetime

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.links.cache import short_link_redirect_cache_delete
from apps.links.models import ShortLink
from apps.links.validators import is_reserved_short_code

SHORT_CODE_ALPHABETS = string.ascii_letters + string.digits
DEFAULT_SHORT_CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 5


def generate_short_code(
    *,
    length: int = DEFAULT_SHORT_CODE_LENGTH,
) -> str:
    return "".join(secrets.choice(SHORT_CODE_ALPHABETS) for _ in range(length))


def short_link_create(
    *,
    owner: User,
    destination_url: str,
    title: str = "",
    expires_at: datetime | None = None,
) -> ShortLink:
    for _ in range(MAX_GENERATION_ATTEMPTS):
        short_code = generate_short_code()

        if is_reserved_short_code(short_code=short_code):
            continue
        try:
            with transaction.atomic():
                link = ShortLink.objects.create(
                    owner=owner,
                    short_code=short_code,
                    destination_url=destination_url,
                    title=title,
                    expires_at=expires_at,
                )
                transaction.on_commit(
                    lambda link_short_code=link.short_code: (
                        short_link_redirect_cache_delete(
                            short_code=link_short_code,
                        )
                    )
                )
                return link
        except IntegrityError:
            continue

    raise RuntimeError("Could not generate a unique short code.")


def short_link_update(
    *,
    link: ShortLink,
    destination_url: str | None = None,
    title: str | None = None,
    is_active: bool | None = None,
    expires_at: datetime | None = None,
    update_expires_at: bool = False,
) -> ShortLink:
    update_fields: list[str] = []

    if destination_url is not None and link.destination_url != destination_url:
        link.destination_url = destination_url
        update_fields.append("destination_url")

    if title is not None and link.title != title:
        link.title = title
        update_fields.append("title")

    if is_active is not None and link.is_active != is_active:
        link.is_active = is_active
        update_fields.append("is_active")

    if update_expires_at and link.expires_at != expires_at:
        link.expires_at = expires_at
        update_fields.append("expires_at")

    if update_fields:
        update_fields.append("updated_at")
        link.save(update_fields=update_fields)
        short_link_redirect_cache_delete(short_code=link.short_code)
    return link


def short_link_delete(*, link: ShortLink) -> None:
    short_code = link.short_code
    link.delete()
    short_link_redirect_cache_delete(short_code=short_code)
