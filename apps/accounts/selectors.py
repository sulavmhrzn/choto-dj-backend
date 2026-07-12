import uuid

from django.db.models import QuerySet

from apps.accounts.models import User


def normalize_email(email: str) -> str:
    return User.objects.normalize_email(email)


def user_list() -> QuerySet[User]:
    return User.objects.all()


def user_get_by_id(*, user_id: uuid.UUID | str) -> User | None:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def user_get_by_email(*, email: str) -> User | None:
    normalized_email = normalize_email(email)

    try:
        return User.objects.get(email=normalized_email)
    except User.DoesNotExist:
        return None


def user_exists_by_email(*, email: str) -> bool:
    normalized_email = normalize_email(email)

    return User.objects.filter(email=normalized_email).exists()


def user_get_active_by_email(*, email: str) -> User | None:
    normalized_email = normalize_email(email)

    try:
        return User.objects.get(email=normalized_email, is_active=True)
    except User.DoesNotExist:
        return None


def user_get_active_by_id(*, user_id: uuid.UUID | str) -> User | None:
    try:
        return User.objects.get(
            id=user_id,
            is_active=True,
        )
    except User.DoesNotExist:
        return None
