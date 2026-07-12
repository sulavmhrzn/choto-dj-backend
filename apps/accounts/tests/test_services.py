import pytest
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import User
from apps.accounts.services import (
    token_issue_for_user,
    user_activate,
    user_create,
    user_deactivate,
    user_update_profile,
)


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@example.com",
        password="strong-password",
        full_name="Sulav Maharjan",
    )


@pytest.mark.django_db
def test_user_create() -> None:
    user = user_create(
        email="new@example.com",
        password="strong-password",
        full_name="New User",
        avatar_url="https://example.com/avatar.jpg",
    )

    assert user.email == "new@example.com"
    assert user.full_name == "New User"
    assert user.avatar_url == "https://example.com/avatar.jpg"
    assert user.check_password("strong-password")


@pytest.mark.django_db
def test_user_create_without_password() -> None:
    user = user_create(
        email="oauth@example.com",
        full_name="OAuth User",
    )

    assert user.has_usable_password() is False


@pytest.mark.django_db
def test_user_create_rejects_duplicate_email(user: User) -> None:
    with pytest.raises(
        ValueError,
        match="User with this email already exists",
    ):
        user_create(
            email=user.email,
            password="another-password",
        )


@pytest.mark.django_db
def test_user_update_profile_updates_given_fields(user: User) -> None:
    updated_user = user_update_profile(
        user=user,
        full_name="Updated Name",
        avatar_url="https://example.com/new-avatar.jpg",
    )

    user.refresh_from_db()

    assert updated_user == user
    assert user.full_name == "Updated Name"
    assert user.avatar_url == "https://example.com/new-avatar.jpg"


@pytest.mark.django_db
def test_user_update_profile_keeps_omitted_fields(user: User) -> None:
    user.avatar_url = "https://example.com/original.jpg"
    user.save(update_fields=["avatar_url"])

    user_update_profile(
        user=user,
        full_name="Updated Name",
    )

    user.refresh_from_db()

    assert user.full_name == "Updated Name"
    assert user.avatar_url == "https://example.com/original.jpg"


@pytest.mark.django_db
def test_user_update_profile_with_no_changes_does_not_save(
    user: User,
    django_assert_num_queries,
) -> None:
    with django_assert_num_queries(0):
        result = user_update_profile(user=user)

    assert result == user


@pytest.mark.django_db
def test_user_deactivate(user: User) -> None:
    result = user_deactivate(user=user)

    user.refresh_from_db()

    assert result == user
    assert user.is_active is False


@pytest.mark.django_db
def test_user_activate(user: User) -> None:
    user.is_active = False
    user.save(update_fields=["is_active"])

    result = user_activate(user=user)

    user.refresh_from_db()

    assert result == user
    assert user.is_active is True


@pytest.mark.django_db
def test_token_issue_for_user_returns_valid_tokens(user: User) -> None:
    tokens = token_issue_for_user(user=user)

    refresh = RefreshToken(tokens["refresh"])
    access = AccessToken(tokens["access"])

    assert str(refresh["user_id"]) == str(user.id)
    assert str(access["user_id"]) == str(user.id)
