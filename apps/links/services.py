import secrets
import string
from datetime import datetime

import structlog
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.links.cache import short_link_redirect_cache_delete
from apps.links.metrics import short_links_created_total
from apps.links.models import ShortLink
from apps.links.selectors import short_link_list_expired_active
from apps.links.validators import is_reserved_short_code

SHORT_CODE_ALPHABETS = string.ascii_letters + string.digits
DEFAULT_SHORT_CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 5

logger = structlog.getLogger()


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
    short_code: str | None = None,
) -> ShortLink:
    if short_code is not None:
        return _short_link_create_with_custom_code(
            owner=owner,
            destination_url=destination_url,
            title=title,
            expires_at=expires_at,
            short_code=short_code,
        )
    return _short_link_create_with_generated_code(
        owner=owner,
        destination_url=destination_url,
        title=title,
        expires_at=expires_at,
    )


def _handle_short_link_created(*, short_code):
    short_link_redirect_cache_delete(
        short_code=short_code,
    )
    short_links_created_total.inc()


def _short_link_create_with_custom_code(
    *,
    owner: User,
    destination_url: str,
    title: str,
    short_code: str,
    expires_at: datetime | None = None,
):
    try:
        with transaction.atomic():
            link = ShortLink.objects.create(
                owner=owner,
                destination_url=destination_url,
                title=title,
                short_code=short_code,
                expires_at=expires_at,
            )
            transaction.on_commit(
                lambda short_code=link.short_code: _handle_short_link_created(
                    short_code=short_code
                )
            )
            logger.info(
                "short_link_created",
                short_link_id=str(link.id),
                owner_id=str(link.owner.id),
                short_code=link.short_code,
                has_custom_alias=True,
            )
        return link
    except IntegrityError as exc:
        logger.warning(
            "short_link_custom_alias_conflict",
            short_code=short_code,
            owner_id=str(owner.id),
        )
        raise ValueError("This custom alias is already in use.") from exc


def _short_link_create_with_generated_code(
    *,
    owner: User,
    destination_url: str,
    title: str = "",
    expires_at: datetime | None = None,
) -> ShortLink:
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        short_code = generate_short_code()

        if is_reserved_short_code(short_code=short_code):
            logger.debug(
                "short_link_generated_code_reserved",
                short_code=short_code,
                attempt=attempt,
            )
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
                    lambda short_code=link.short_code: _handle_short_link_created(
                        short_code=short_code
                    )
                )
                logger.info(
                    "short_link_created",
                    short_link_id=str(link.id),
                    owner_id=str(link.owner.id),
                    short_code=link.short_code,
                    has_custom_alias=False,
                )
                return link
        except IntegrityError:
            logger.debug(
                "short_link_generated_code_collison",
                short_code=short_code,
                attempt=attempt,
            )
            continue

    logger.error(
        "short_link_generated_code_exhausted",
        owner_id=str(owner.id),
        max_generation=MAX_GENERATION_ATTEMPTS,
    )
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
        logger.info(
            "short_link_updated",
            short_link_id=str(link.id),
            short_code=link.short_code,
            owner_id=str(link.owner.id),
            update_fields=update_fields,
        )

        short_link_redirect_cache_delete(short_code=link.short_code)
    return link


def short_link_delete(*, link: ShortLink) -> None:
    short_code = link.short_code
    link.delete()
    logger.info("short_link_deleted", short_code=short_code)

    short_link_redirect_cache_delete(short_code=short_code)


def _clear_short_link_redirect_caches(*, short_codes: list[str]):
    for short_code in short_codes:
        short_link_redirect_cache_delete(short_code=short_code)


def short_link_deactivate_expired() -> int:
    links = list(
        short_link_list_expired_active().only("id", "short_code"),
    )

    if not links:
        return 0

    link_ids = [link.id for link in links]
    short_codes = [link.short_code for link in links]

    with transaction.atomic():
        updated_count = ShortLink.objects.filter(
            id__in=link_ids, is_active=True
        ).update(is_active=False)

        transaction.on_commit(
            lambda short_codes=short_codes: _clear_short_link_redirect_caches(
                short_codes=short_codes
            )
        )

    return updated_count
