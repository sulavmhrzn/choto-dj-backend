from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import APIKey, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = (
        "email",
        "full_name",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    search_fields = (
        "email",
        "full_name",
    )

    ordering = ("-date_joined",)

    readonly_fields = (
        "id",
        "date_joined",
        "created_at",
        "updated_at",
        "last_login",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "email",
                    "password",
                    "full_name",
                    "avatar_url",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important Dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            "Create User",
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner",
        "prefix",
        "is_active",
        "last_used_at",
        "created_at",
        "revoked_at",
    ]
    list_filter = [
        "is_active",
        "created_at",
        "revoked_at",
    ]
    search_fields = [
        "name",
        "prefix",
        "owner__email",
    ]
    ordering = [
        "-created_at",
    ]
    readonly_fields = [
        "id",
        "owner",
        "prefix",
        "hashed_secret",
        "last_used_at",
        "created_at",
        "revoked_at",
    ]

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "id",
                    "owner",
                    "name",
                    "prefix",
                    "is_active",
                ]
            },
        ),
        (
            "Security",
            {
                "fields": [
                    "hashed_secret",
                ]
            },
        ),
        (
            "Usage",
            {
                "fields": [
                    "last_used_at",
                    "created_at",
                    "revoked_at",
                ]
            },
        ),
    ]
