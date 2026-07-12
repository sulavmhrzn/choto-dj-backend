import pytest

from apps.accounts.models import User
from apps.accounts.serializers import (
    UserMeSerializer,
    UserProfileUpdateSerializer,
)


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@example.com",
        password="strong-password",
        full_name="Sulav Maharjan",
        avatar_url="https://example.com/avatar.jpg",
    )


@pytest.mark.django_db
def test_user_me_serializer_returns_expected_fields(user: User) -> None:
    data = UserMeSerializer(user).data

    assert set(data) == {
        "id",
        "email",
        "full_name",
        "avatar_url",
        "date_joined",
    }

    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["full_name"] == user.full_name
    assert data["avatar_url"] == user.avatar_url


def test_profile_update_serializer_accepts_full_name() -> None:
    serializer = UserProfileUpdateSerializer(data={"full_name": "Updated Name"})

    assert serializer.is_valid() is True
    assert serializer.validated_data == {
        "full_name": "Updated Name",
    }


def test_profile_update_serializer_accepts_avatar_url() -> None:
    serializer = UserProfileUpdateSerializer(
        data={"avatar_url": "https://example.com/new-avatar.jpg"}
    )

    assert serializer.is_valid() is True
    assert serializer.validated_data == {
        "avatar_url": "https://example.com/new-avatar.jpg",
    }


def test_profile_update_serializer_accepts_blank_values() -> None:
    serializer = UserProfileUpdateSerializer(
        data={
            "full_name": "",
            "avatar_url": "",
        }
    )

    assert serializer.is_valid() is True


def test_profile_update_serializer_rejects_empty_request() -> None:
    serializer = UserProfileUpdateSerializer(data={})

    assert serializer.is_valid() is False
    assert serializer.errors == {
        "non_field_errors": ["At least one field is required."]
    }


def test_profile_update_serializer_rejects_invalid_avatar_url() -> None:
    serializer = UserProfileUpdateSerializer(data={"avatar_url": "not-a-url"})

    assert serializer.is_valid() is False
    assert "avatar_url" in serializer.errors


def test_profile_update_serializer_rejects_long_full_name() -> None:
    serializer = UserProfileUpdateSerializer(data={"full_name": "a" * 256})

    assert serializer.is_valid() is False
    assert "full_name" in serializer.errors
