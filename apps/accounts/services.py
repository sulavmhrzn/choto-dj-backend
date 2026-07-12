from typing import Any

from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.selectors import user_get_by_email


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
        raise ValueError("User with this email already exists")

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        avatar_url=avatar_url,
        **extra_fields,
    )
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

    return user


def user_deactivate(*, user: User) -> User:
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    return user


def user_activate(*, user: User) -> User:
    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])
    return user


def token_issue_for_user(*, user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
