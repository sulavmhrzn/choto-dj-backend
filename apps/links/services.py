import secrets
import string
from datetime import datetime

import structlog
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.exceptions import PlanLimitExceededError
from apps.billing.selectors import subscription_get_for_user_for_update
from apps.billing.services import subscription_can_create_short_link
from apps.links.cache import short_link_redirect_cache_delete
from apps.links.metrics import short_links_created_total
from apps.links.models import ShortLink
from apps.links.selectors import (
    short_link_count_for_user,
    short_link_list_expired_active,
)
from apps.links.validators import is_reserved_short_code
from apps.webhooks.models import WebhookEventType
from apps.webhooks.services import webhook_event_dispatch

SHORT_CODE_ALPHABETS = string.ascii_letters + string.digits
DEFAULT_SHORT_CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 5

logger = structlog.getLogger()


def generate_short_code(
    *,
    length: int = DEFAULT_SHORT_CODE_LENGTH,
) -> str:
    return "".join(secrets.choice(SHORT_CODE_ALPHABETS) for _ in range(length))


def _build_short_link_created_webhook_data(
    *, short_link: ShortLink
) -> dict[str, object]:
    return {
        "short_link_id": str(short_link.id),
        "short_code": short_link.short_code,
        "destination_url": short_link.destination_url,
        "title": short_link.title,
        "is_active": short_link.is_active,
        "expires_at": (
            short_link.expires_at.isoformat()
            if short_link.expires_at is not None
            else None
        ),
        "created_at": short_link.created_at.isoformat(),
    }


def _build_short_link_updated_webhook_data(
    *, short_link: ShortLink, changed_fields: list[str]
) -> dict[str, object]:
    return {
        "short_link_id": str(short_link.id),
        "short_code": short_link.short_code,
        "destination_url": short_link.destination_url,
        "title": short_link.title,
        "is_active": short_link.is_active,
        "expires_at": (
            short_link.expires_at.isoformat()
            if short_link.expires_at is not None
            else None
        ),
        "updated_at": short_link.updated_at.isoformat(),
        "changed_fields": changed_fields,
    }


def _build_short_link_deleted_webhook_data(
    *, short_link: ShortLink
) -> dict[str, object]:
    return {
        "short_link_id": str(short_link.id),
        "short_code": short_link.short_code,
        "destination_url": short_link.destination_url,
        "title": short_link.title,
        "is_active": short_link.is_active,
        "expires_at": (
            short_link.expires_at.isoformat()
            if short_link.expires_at is not None
            else None
        ),
        "created_at": short_link.created_at.isoformat(),
    }


def _handle_short_link_created(*, short_link: ShortLink):
    short_link_redirect_cache_delete(
        short_code=short_link.short_code,
    )
    short_links_created_total.inc()
    try:
        webhook_event_dispatch(
            owner=short_link.owner,
            event_type=WebhookEventType.SHORT_LINK_CREATED,
            data=_build_short_link_created_webhook_data(short_link=short_link),
            created_at=short_link.created_at,
        )
    except Exception:  # noqa
        logger.exception(
            "short_link_created_webhook_dispatch_failed",
            short_link_id=str(short_link.id),
        )


def _handle_short_link_updated(*, short_link: ShortLink, updated_fields: list[str]):
    short_link_redirect_cache_delete(short_code=short_link.short_code)
    try:
        webhook_event_dispatch(
            owner=short_link.owner,
            event_type=WebhookEventType.SHORT_LINK_UPDATED,
            data=_build_short_link_updated_webhook_data(
                short_link=short_link, changed_fields=updated_fields
            ),
            created_at=short_link.updated_at,
        )
    except Exception:
        logger.exception(
            "short_link_updated_webhook_dispatch_failed",
            short_link_id=str(short_link.id),
        )


def _handle_short_link_deleted(
    *,
    owner: User,
    short_code: str,
    webhook_data: dict[str, object],
    deleted_at: datetime,
):
    short_link_redirect_cache_delete(short_code=short_code)
    try:
        webhook_event_dispatch(
            owner=owner,
            event_type=WebhookEventType.SHORT_LINK_DELETED,
            data=webhook_data,
            created_at=deleted_at,
        )
    except Exception:
        logger.exception(
            "short_link_deleted_webhook_dispatch_failed",
            short_link_id=webhook_data["short_link_id"],
        )


@transaction.atomic
def short_link_create(
    *,
    owner: User,
    destination_url: str,
    title: str = "",
    expires_at: datetime | None = None,
    short_code: str | None = None,
) -> ShortLink:

    subscription = subscription_get_for_user_for_update(user=owner)

    if subscription is None:
        raise RuntimeError("User does not have a subscription")

    current_short_link_count = short_link_count_for_user(user=owner)

    if not subscription_can_create_short_link(
        subscription=subscription,
        current_short_link_count=current_short_link_count,
    ):
        raise PlanLimitExceededError("Short link limit reached for current plan.")

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
                lambda short_link=link: _handle_short_link_created(
                    short_link=short_link
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
                    lambda short_link=link: _handle_short_link_created(
                        short_link=short_link
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


@transaction.atomic
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
        transaction.on_commit(
            lambda link=link, changed_fields=update_fields.copy(): (
                _handle_short_link_updated(
                    short_link=link, updated_fields=changed_fields
                )
            )
        )
    return link


@transaction.atomic
def short_link_delete(*, link: ShortLink) -> None:
    owner = link.owner
    short_code = link.short_code
    deleted_at = timezone.now()
    webhook_data = _build_short_link_deleted_webhook_data(short_link=link)

    link.delete()
    logger.info("short_link_deleted", short_code=short_code)
    transaction.on_commit(
        lambda owner=owner, short_code=short_code, webhook_data=webhook_data, deleted_at=deleted_at: (
            _handle_short_link_deleted(
                owner=owner,
                short_code=short_code,
                webhook_data=webhook_data,
                deleted_at=deleted_at,
            )
        )
    )


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
