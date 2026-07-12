import pytest

from apps.accounts.models import User


@pytest.mark.django_db
def test_create_user_with_email() -> None:
    user = User.objects.create_user(
        email="sulav@example.com",
        password="strong-password",
        full_name="Sulav Maharjan",
    )
    assert user.email == "sulav@example.com"
    assert user.full_name == "Sulav Maharjan"
    assert user.check_password("strong-password")
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_create_user_normalize_email() -> None:
    user = User.objects.create_user(
        email="Sulav@EXAMPLE.COM", password="string-password"
    )
    assert user.email == "Sulav@example.com"


@pytest.mark.django_db
def test_create_user_without_password_sets_unusable_password() -> None:
    user = User.objects.create_user(email="oauth@example.com")
    assert user.has_usable_password() is False


@pytest.mark.django_db
def test_create_user_without_email_raises_error() -> None:
    with pytest.raises(ValueError, match="Email is required"):
        User.objects.create_user(email="", password="strong-password")


@pytest.mark.django_db
def test_create_superuser() -> None:
    user = User.objects.create_superuser(
        email="admin@example.com", password="strong-password"
    )
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True
