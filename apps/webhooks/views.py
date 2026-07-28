from typing import cast
from uuid import UUID

from django.utils.autoreload import raise_last_exception
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import User
from apps.webhooks.selectors import (
    webhook_endpoint_get_for_user,
    webhook_endpoint_list_for_user,
)
from apps.webhooks.serializers import (
    WebhookEndpointCreateSerializer,
    WebhookEndpointSerializer,
    WebhookEndpointUpdateSerializer,
)
from apps.webhooks.services import webhook_endpoint_create, webhook_endpoint_update


class WebhookEndpointListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request: Request) -> Response:
        serializer = WebhookEndpointCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = cast(User, request.user)

        created = webhook_endpoint_create(
            owner=user,
            name=serializer.validated_data["name"],
            url=serializer.validated_data["url"],
            events=serializer.validated_data["events"],
        )

        response_data = {
            **WebhookEndpointSerializer(created.endpoint).data,
            "secret": created.secret,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        endpoints = webhook_endpoint_list_for_user(user=user)
        serializer = WebhookEndpointSerializer(endpoints, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class WebhookEndpointDetailAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, endpoint_id: UUID) -> Response:
        user = cast(User, request.user)

        endpoint = webhook_endpoint_get_for_user(user=user, endpoint_id=endpoint_id)

        if endpoint is None:
            raise NotFound("Webhook endpoint not found.")

        return Response(
            WebhookEndpointSerializer(endpoint).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request: Request, endpoint_id: UUID) -> Response:
        user = cast(User, request.user)

        endpoint = webhook_endpoint_get_for_user(
            user=user,
            endpoint_id=endpoint_id,
        )

        if endpoint is None:
            raise NotFound("Webhook endpoint not found.")

        serializer = WebhookEndpointUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        updated_endpoint = webhook_endpoint_update(
            endpoint=endpoint,
            **serializer.validated_data,
        )

        return Response(
            WebhookEndpointSerializer(updated_endpoint).data,
            status=status.HTTP_200_OK,
        )
