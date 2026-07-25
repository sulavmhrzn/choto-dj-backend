from django.contrib import admin

from apps.core.models import IdempotencyRecord


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = [
        "key",
        "owner",
        "status",
        "short_link",
        "created_at",
        "expires_at",
    ]
    list_filter = [
        "status",
        "created_at",
        "expires_at",
    ]
    search_fields = [
        "key",
        "owner__email",
        "short_link__short_code",
    ]
    ordering = [
        "-created_at",
    ]
    readonly_fields = [
        "id",
        "owner",
        "key",
        "request_hash",
        "status",
        "response_status",
        "response_data",
        "short_link",
        "created_at",
        "expires_at",
    ]

    fieldsets = [
        (
            "Identity",
            {
                "fields": [
                    "id",
                    "owner",
                    "key",
                    "request_hash",
                ],
            },
        ),
        (
            "Operation",
            {
                "fields": [
                    "status",
                    "short_link",
                    "response_status",
                    "response_data",
                ],
            },
        ),
        (
            "Retention",
            {
                "fields": [
                    "created_at",
                    "expires_at",
                ],
            },
        ),
    ]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ) -> bool:
        return False
