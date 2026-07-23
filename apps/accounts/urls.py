from django.urls import path

from apps.accounts.views import (
    APIKeyListCreateAPIView,
    APIKeyRevokeAPIView,
    GoogleOAuthTokenAPIView,
    UserMeAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("me/", UserMeAPIView.as_view(), name="me"),
    path(
        "oauth/google/token/",
        GoogleOAuthTokenAPIView.as_view(),
        name="google-oauth-token",
    ),
    path(
        "api-keys/",
        APIKeyListCreateAPIView.as_view(),
        name="api-key-list-create",
    ),
    path(
        "api-keys/<uuid:api_key_id>/revoke/",
        APIKeyRevokeAPIView.as_view(),
        name="api-key-revoke",
    ),
]
