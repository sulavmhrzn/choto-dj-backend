import pytest
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.test import RequestFactory

from apps.accounts.adapters import SocialAccountAdapter
from apps.accounts.models import User


@pytest.mark.django_db
def test_populate_user_sets_google_profile_fields() -> None:
    request = RequestFactory().get("/")
    user = User(email="sulav@example.com")

    account = SocialAccount(
        provider="google",
        uid="google-user-id",
        user=user,
        extra_data={
            "name": "Sulav Maharjan",
            "picture": "https://example.com/avatar.jpg",
            "email": "sulav@example.com",
        },
    )
    sociallogin = SocialLogin(
        user=user,
        account=account,
    )

    adapter = SocialAccountAdapter(request)

    populated_user = adapter.populate_user(
        request=request,
        sociallogin=sociallogin,
        data={"email": "sulav@example.com", "name": "Sulav Maharjan"},
    )
    assert populated_user.full_name == "Sulav Maharjan"
    assert populated_user.avatar_url == "https://example.com/avatar.jpg"


@pytest.mark.django_db
def test_pre_social_login_updates_existing_user_profile() -> None:
    request = RequestFactory().get("/")

    user = User.objects.create_user(
        email="sulav@example.com",
        full_name="Old Name",
        avatar_url="https://example.com/old-avatar.jpg",
    )

    account = SocialAccount.objects.create(
        provider="google",
        uid="google-user-id",
        user=user,
        extra_data={
            "name": "Sulav Maharjan",
            "picture": "https://example.com/new-avatar.jpg",
        },
    )
    sociallogin = SocialLogin(
        user=user,
        account=account,
    )
    adapter = SocialAccountAdapter(request)
    adapter.pre_social_login(request, sociallogin)
    user.refresh_from_db()

    assert user.full_name == "Sulav Maharjan"
    assert user.avatar_url == "https://example.com/new-avatar.jpg"
