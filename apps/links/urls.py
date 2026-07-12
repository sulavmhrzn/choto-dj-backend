from django.urls import path

from apps.links.views import ShortLinkDetailAPIView, ShortLinkListCreateAPIView

app_name = "links"

urlpatterns = [
    path("", ShortLinkListCreateAPIView.as_view(), name="list-create"),
    path("<uuid:link_id>/", ShortLinkDetailAPIView.as_view(), name="detail"),
]
