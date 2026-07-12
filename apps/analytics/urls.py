from django.urls import path

from apps.analytics.views import ShortLinkAnalyticsAPIView

app_name = "analytics"

urlpatterns = [
    path(
        "links/<uuid:link_id>/", ShortLinkAnalyticsAPIView.as_view(), name="short-link"
    )
]
