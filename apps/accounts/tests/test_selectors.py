import pytest

from apps.accounts.models import APIKey, User
from apps.accounts.selectors import (
    api_key_list_for_user,
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


@pytest.fixture
def another_user() -> User:
    return User.objects.create_user(
        email="sweta@example.com",
        password="strong-password",
        full_name="Sweta Maharjan",
        avatar_url="https://example.com/avatar.jpg",
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


@pytest.mark.django_db
def test_api_key_list_for_user_returns_only_users_keys(user, another_user):

    first_key = APIKey.objects.create(
        owner=user,
        name="First",
        prefix="firstkey1234",
        hashed_secret="hash-1",
    )
    second_key = APIKey.objects.create(
        owner=user,
        name="Second",
        prefix="secondkey123",
        hashed_secret="hash-2",
    )
    APIKey.objects.create(
        owner=another_user,
        name="Other",
        prefix="otherkey1234",
        hashed_secret="hash-3",
    )

    results = list(
        api_key_list_for_user(
            user=user,
        )
    )

    assert results == [
        second_key,
        first_key,
    ]
