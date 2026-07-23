from typing import cast
from uuid import UUID

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.models import User
from apps.accounts.selectors import api_key_get_for_user, api_key_list_for_user
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    UserMeSerializer,
    UserProfileUpdateSerializer,
)
from apps.accounts.services import (
    api_key_create,
    api_key_revoke,
    token_issue_for_user,
    user_update_profile,
)
from apps.links.serializers import APIKeyCreateSerailizer, APIKeySerializer


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


class APIKeyListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = APIKeyCreateSerailizer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = cast(User, request.user)

        created_api_key = api_key_create(
            owner=user, name=serializer.validated_data["name"]
        )
        response_data = {
            **APIKeySerializer(created_api_key.api_key).data,
            "key": created_api_key.secret,
        }
        return Response(data=response_data, status=status.HTTP_201_CREATED)

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        api_keys = api_key_list_for_user(user=user)

        serializer = APIKeySerializer(api_keys, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class APIKeyRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, api_key_id: UUID) -> Response:
        user = cast(User, request.user)

        api_key = api_key_get_for_user(user=user, api_key_id=api_key_id)

        if api_key is None:
            raise NotFound("API Key not found.")

        revoked_api_key = api_key_revoke(api_key=api_key)

        return Response(
            APIKeySerializer(revoked_api_key).data, status=status.HTTP_200_OK
        )
