from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.http import HttpRequest

from apps.accounts.models import User


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(
        self, request: HttpRequest, sociallogin: SocialLogin, data: dict[str, str]
    ) -> User:
        user = super().populate_user(
            request=request, sociallogin=sociallogin, data=data
        )

        extra_data = sociallogin.account.extra_data
        user.full_name = extra_data.get("name", "")
        user.avatar_url = extra_data.get("picture", "")
        return user

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin):
        super().pre_social_login(request, sociallogin)

        if not sociallogin.is_existing:
            return

        user = sociallogin.user
        extra_data = sociallogin.account.extra_data

        full_name = extra_data.get("name", "")
        avatar_url = extra_data.get("picture", "")

        update_fields: list[str] = []

        if full_name and user.full_name != full_name:
            user.full_name = full_name
            update_fields.append("full_name")

        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            update_fields.append("avatar_url")

        if update_fields:
            update_fields.append("updated_at")
            user.save(update_fields=update_fields)
