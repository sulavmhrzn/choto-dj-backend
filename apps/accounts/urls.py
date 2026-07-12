from django.urls import path

from apps.accounts.views import GoogleOAuthTokenAPIView, UserMeAPIView

app_name = "accounts"

urlpatterns = [
    path("me/", UserMeAPIView.as_view(), name="me"),
    path(
        "oauth/google/token/",
        GoogleOAuthTokenAPIView.as_view(),
        name="google-oauth-token",
    ),
]
