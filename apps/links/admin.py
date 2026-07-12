from django.contrib import admin

from apps.links.models import ShortLink


@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    list_display = (
        "short_code",
        "owner",
        "destination_url",
        "is_active",
        "expires_at",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
        "expires_at",
    )

    search_fields = (
        "short_code",
        "title",
        "destination_url",
        "owner__email",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = ("owner",)

    ordering = ("-created_at",)

    fieldsets = (
        (
            "Link",
            {
                "fields": (
                    "id",
                    "owner",
                    "short_code",
                    "destination_url",
                    "title",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "expires_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
