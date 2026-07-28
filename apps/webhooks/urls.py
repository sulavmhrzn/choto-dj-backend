from django.urls import path

from apps.webhooks.views import (
    WebhookEndpointDetailAPIView,
    WebhookEndpointListCreateAPIView,
)

app_name = "webhooks"
urlpatterns = [
    path(
        "endpoints/",
        WebhookEndpointListCreateAPIView.as_view(),
        name="endpoint-list-create",
    ),
    path(
        "endpoints/<uuid:endpoint_id>/",
        WebhookEndpointDetailAPIView.as_view(),
        name="endpoint-detail",
    ),
]
