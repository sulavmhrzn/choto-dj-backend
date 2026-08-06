from django.contrib import admin

from apps.webhooks.models import (
    WebhookDelivery,
    WebhookEndpoint,
)


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner",
        "url",
        "is_active",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        "is_active",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "name",
        "owner__email",
        "url",
    ]
    ordering = [
        "-created_at",
    ]
    readonly_fields = [
        "id",
        "owner",
        "encrypted_secret",
        "created_at",
        "updated_at",
    ]

    fieldsets = [
        (
            "Endpoint",
            {
                "fields": [
                    "id",
                    "owner",
                    "name",
                    "url",
                    "events",
                    "is_active",
                ],
            },
        ),
        (
            "Security",
            {
                "fields": [
                    "encrypted_secret",
                ],
            },
        ),
        (
            "Timestamps",
            {
                "fields": [
                    "created_at",
                    "updated_at",
                ],
            },
        ),
    ]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "event_type",
        "endpoint",
        "status",
        "attempt_count",
        "response_status",
        "created_at",
        "delivered_at",
    ]
    list_filter = [
        "status",
        "event_type",
        "response_status",
        "created_at",
        "delivered_at",
    ]
    search_fields = [
        "id",
        "event_id",
        "endpoint__name",
        "endpoint__owner__email",
        "endpoint__url",
    ]
    ordering = [
        "-created_at",
    ]
    readonly_fields = [
        "id",
        "endpoint",
        "event_id",
        "event_type",
        "payload",
        "status",
        "attempt_count",
        "response_status",
        "response_body",
        "error_message",
        "next_attempt_at",
        "delivered_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = [
        (
            "Event",
            {
                "fields": [
                    "id",
                    "event_id",
                    "event_type",
                    "endpoint",
                    "payload",
                ],
            },
        ),
        (
            "Delivery result",
            {
                "fields": [
                    "status",
                    "attempt_count",
                    "response_status",
                    "response_body",
                    "error_message",
                ],
            },
        ),
        (
            "Scheduling",
            {
                "fields": [
                    "next_attempt_at",
                    "delivered_at",
                    "created_at",
                    "updated_at",
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
