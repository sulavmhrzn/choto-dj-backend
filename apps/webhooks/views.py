from typing import cast
from uuid import UUID

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import User
from apps.billing.exceptions import PlanLimitExceededError
from apps.webhooks.selectors import (
    webhook_delivery_get_for_user,
    webhook_delivery_list_for_endpoint,
    webhook_endpoint_get_for_user,
    webhook_endpoint_list_for_user,
)
from apps.webhooks.serializers import (
    WebhookDeliveryDetailSerializer,
    WebhookDeliveryFilterSerializer,
    WebhookDeliveryListSerializer,
    WebhookEndpointCreateSerializer,
    WebhookEndpointSerializer,
    WebhookEndpointUpdateSerializer,
)
from apps.webhooks.services import webhook_endpoint_create, webhook_endpoint_update
from config.api.pagination import DefaultPageNumberPagination


class WebhookEndpointListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @extend_schema(
        tags=["Webhooks"],
        request=WebhookEndpointCreateSerializer,
        responses=inline_serializer(
            name="WebhookEndpointCreateResponse",
            fields={
                **WebhookEndpointSerializer().fields,
                "secret": serializers.CharField(),
            },
        ),
    )
    def post(self, request: Request) -> Response:
        serializer = WebhookEndpointCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = cast(User, request.user)
        try:
            created = webhook_endpoint_create(
                owner=user,
                name=serializer.validated_data["name"],
                url=serializer.validated_data["url"],
                events=serializer.validated_data["events"],
            )
        except PlanLimitExceededError as exc:
            raise PermissionDenied(str(exc)) from exc

        response_data = {
            **WebhookEndpointSerializer(created.endpoint).data,
            "secret": created.secret,
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Webhooks"],
        operation_id="webhooks_endpoints_list",
        responses=WebhookEndpointSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        endpoints = webhook_endpoint_list_for_user(user=user)
        serializer = WebhookEndpointSerializer(endpoints, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class WebhookEndpointDetailAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Webhooks"],
        operation_id="webhooks_endpoints_retrieve",
        responses=WebhookEndpointSerializer,
    )
    def get(self, request: Request, endpoint_id: UUID) -> Response:
        user = cast(User, request.user)

        endpoint = webhook_endpoint_get_for_user(user=user, endpoint_id=endpoint_id)

        if endpoint is None:
            raise NotFound("Webhook endpoint not found.")

        return Response(
            WebhookEndpointSerializer(endpoint).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Webhooks"],
        request=WebhookEndpointUpdateSerializer,
        responses=WebhookEndpointSerializer,
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


class WebhookEndpointDeliveryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Webhooks"],
        parameters=[WebhookDeliveryFilterSerializer],
        responses=WebhookDeliveryListSerializer(many=True),
    )
    def get(self, request: Request, endpoint_id: UUID) -> Response:
        endpoint = webhook_endpoint_get_for_user(
            user=request.user, endpoint_id=endpoint_id
        )
        if not endpoint:
            raise NotFound("Webhook endpoint not found.")

        filter_serializer = WebhookDeliveryFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        deliveries = webhook_delivery_list_for_endpoint(
            user=request.user,
            endpoint_id=endpoint.id,
            **filter_serializer.validated_data,
        )
        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(deliveries, request, view=self)

        serializer = WebhookDeliveryListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class WebhookDeliveryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Webhooks"], responses=WebhookDeliveryDetailSerializer)
    def get(self, request: Request, delivery_id: UUID) -> Response:
        delivery = webhook_delivery_get_for_user(
            user=request.user, delivery_id=delivery_id
        )

        if delivery is None:
            raise NotFound("Webhook delivery not found.")

        serializer = WebhookDeliveryDetailSerializer(delivery)

        return Response(serializer.data)
