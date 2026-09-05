from django.urls import path

from apps.core.views import APIRootAPIView, LivenessAPIView, ReadinessAPIView

app_name = "core"

urlpatterns = [
    path(
        "",
        APIRootAPIView.as_view(),
        name="api-root",
    ),
    path(
        "health/live/",
        LivenessAPIView.as_view(),
        name="health-live",
    ),
    path(
        "health/ready/",
        ReadinessAPIView.as_view(),
        name="health-ready",
    ),
]
