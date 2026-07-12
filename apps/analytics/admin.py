from django.contrib import admin

from apps.analytics.models import ClickEvent


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = (
        "short_link",
        "ip_address",
        "referrer",
        "clicked_at",
    )

    list_filter = ("clicked_at",)

    search_fields = (
        "short_link__short_code",
        "short_link__owner__email",
        "ip_address",
        "referrer",
        "user_agent",
    )

    readonly_fields = (
        "id",
        "short_link",
        "clicked_at",
        "referrer",
        "user_agent",
        "ip_address",
    )

    autocomplete_fields = ("short_link",)

    ordering = ("-clicked_at",)

    date_hierarchy = "clicked_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ) -> bool:
        return False
