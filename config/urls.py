from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

from apps.accounts.views import CustomTokenObtainPairAPIView, CustomTokenRefreshAPIView
from apps.links.views import ShortLinkRedirectAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/links/", include("apps.links.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    path(
        "api/v1/auth/token/",
        CustomTokenObtainPairAPIView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/v1/auth/token/refresh/", CustomTokenRefreshAPIView.as_view(), name="token_refresh"
    ),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/", include("allauth.urls")),
    path(
        "<str:short_code>/",
        ShortLinkRedirectAPIView.as_view(),
        name="short-link-redirect",
    ),
]
