from typing import cast

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.models import User
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    UserMeSerializer,
    UserProfileUpdateSerializer,
)
from apps.accounts.services import token_issue_for_user, user_update_profile


class UserMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = UserMeSerializer(user)
        return Response(
            data=serializer.data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request: Request) -> Response:
        user = cast(User, request.user)

        serializer = UserProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_user = user_update_profile(
            user=user,
            full_name=serializer.validated_data.get("full_name"),
            avatar_url=serializer.validated_data.get("avatar_url"),
        )

        response_serializer = UserMeSerializer(updated_user)

        return Response(
            data=response_serializer.data,
            status=status.HTTP_200_OK,
        )


class CustomTokenObtainPairAPIView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class CustomTokenRefreshAPIView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"


class GoogleOAuthTokenAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "google_oauth_token"

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        tokens = token_issue_for_user(user=user)
        return Response(
            data={
                **tokens,
                "user": UserMeSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
