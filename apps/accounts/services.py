import hashlib
import secrets
from typing import Any

import structlog
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.constants import (
    API_KEY_GENERATION_ATTEMPTS,
    API_KEY_PREFIX_LENGTH,
    API_KEY_SECRET_BYTES,
)
from apps.accounts.models import APIKey, User
from apps.accounts.selectors import user_get_by_email
from apps.accounts.types import CreatedAPIKey

logger = structlog.getLogger()


@transaction.atomic
def user_create(
    *,
    email: str,
    password: str | None = None,
    full_name: str = "",
    avatar_url: str = "",
    **extra_fields: Any,
) -> User:
    existing_user = user_get_by_email(email=email)

    if existing_user is not None:
        logger.warning("user_already_exists", email=email)
        raise ValueError("User with this email already exists")

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        avatar_url=avatar_url,
        **extra_fields,
    )
    logger.info("user_created", email=email, created_at=user.created_at)
    return user


def user_update_profile(
    *,
    user: User,
    full_name: str | None = None,
    avatar_url: str | None = None,
) -> User:
    update_fields: list[str] = []

    if full_name is not None and user.full_name != full_name:
        user.full_name = full_name
        update_fields.append("full_name")

    if avatar_url is not None and user.avatar_url != avatar_url:
        user.avatar_url = avatar_url
        update_fields.append("avatar_url")

    if not update_fields:
        return user

    update_fields.append("updated_at")
    user.save(update_fields=update_fields)

    logger.info("user_updated", update_fields=update_fields)
    return user


def user_deactivate(*, user: User) -> User:
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])

    logger.info("user_deactivated", email=user.email, updated_at=user.updated_at)
    return user


def user_activate(*, user: User) -> User:
    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])

    logger.info("user_activated", email=user.email, updated_at=user.updated_at)
    return user


def token_issue_for_user(*, user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)

    logger.info("token_issued", email=user.email)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def hash_api_key_secret(*, secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key_prefix() -> str:
    return secrets.token_hex(API_KEY_PREFIX_LENGTH // 2)


def generate_api_key_secret() -> str:
    return secrets.token_urlsafe(API_KEY_SECRET_BYTES)


@transaction.atomic
def api_key_create(
    *,
    owner: User,
    name: str,
) -> CreatedAPIKey:
    for _ in range(API_KEY_GENERATION_ATTEMPTS):
        prefix = generate_api_key_prefix()
        secret = generate_api_key_secret()

        try:
            api_key = APIKey.objects.create(
                owner=owner,
                name=name,
                prefix=prefix,
                hashed_secret=hash_api_key_secret(secret=secret),
            )
        except IntegrityError:
            continue

        complete_secret = f"choto_{prefix}.{secret}"

        return CreatedAPIKey(api_key=api_key, secret=complete_secret)

    raise RuntimeError("Could not generate a unique API key")


def api_key_revoke(*, api_key: APIKey) -> APIKey:
    if not api_key.is_active:
        return api_key

    api_key.is_active = False
    api_key.revoked_at = timezone.now()

    api_key.save(update_fields=["is_active", "revoked_at"])

    return api_key
