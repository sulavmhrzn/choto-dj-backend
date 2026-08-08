from django.urls import path

from apps.webhooks.views import (
    WebhookDeliveryDetailAPIView,
    WebhookEndpointDeliveryListAPIView,
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
    path(
        "endpoints/<uuid:endpoint_id>/deliveries/",
        WebhookEndpointDeliveryListAPIView.as_view(),
        name="endpoint-deliveries",
    ),
    path(
        "deliveries/<uuid:delivery_id>/",
        WebhookDeliveryDetailAPIView.as_view(),
        name="delivery-detail",
    ),
]
