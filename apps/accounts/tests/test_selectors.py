import pytest

from apps.accounts.models import User
from apps.accounts.selectors import (
    user_exists_by_email,
    user_get_active_by_email,
    user_get_active_by_id,
    user_get_by_email,
    user_get_by_id,
    user_list,
)


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@example.com",
        password="strong-password",
        full_name="Sulav Maharjan",
    )


@pytest.mark.django_db
def test_user_list_returns_users(user: User) -> None:
    users = user_list()

    assert list(users) == [user]


@pytest.mark.django_db
def test_user_get_by_id_returns_user(user: User) -> None:
    result = user_get_by_id(user_id=user.id)
    assert result == user


@pytest.mark.django_db
def test_user_get_by_id_returns_none_when_missing() -> None:
    result = user_get_by_id(user_id="00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.django_db
def test_user_get_by_email_returns_user(user: User) -> None:
    result = user_get_by_email(email="sulav@EXAMPLE.COM")
    assert result == user


@pytest.mark.django_db
def test_user_get_by_email_returns_none_when_missing() -> None:
    result = user_get_by_email(email="missing@example.com")

    assert result is None


@pytest.mark.django_db
def test_user_exists_by_email_returns_true(user: User) -> None:
    assert user_exists_by_email(email="sulav@example.com") is True


@pytest.mark.django_db
def test_user_exists_by_email_returns_false() -> None:
    assert user_exists_by_email(email="missing@example.com") is False


@pytest.mark.django_db
def test_user_get_active_by_email_returns_active_user(user: User) -> None:
    result = user_get_active_by_email(email=user.email)

    assert result == user


@pytest.mark.django_db
def test_user_get_active_by_email_ignores_inactive_user(user: User) -> None:
    user.is_active = False
    user.save(update_fields=["is_active"])

    result = user_get_active_by_email(email=user.email)

    assert result is None


@pytest.mark.django_db
def test_user_get_active_by_id_returns_active_user(user: User) -> None:
    result = user_get_active_by_id(user_id=user.id)

    assert result == user


@pytest.mark.django_db
def test_user_get_active_by_id_ignores_inactive_user(user: User) -> None:
    user.is_active = False
    user.save(update_fields=["is_active"])

    result = user_get_active_by_id(user_id=user.id)

    assert result is None
