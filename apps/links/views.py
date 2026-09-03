from typing import cast
from uuid import UUID

import structlog
from django.db import transaction
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.analytics.metrics import click_event_dispatch_total
from apps.analytics.tasks import click_event_create_task
from apps.analytics.utils import get_client_ip
from apps.billing.exceptions import PlanLimitExceededError
from apps.core.exceptions import IdempotencyConflict
from apps.core.idempotency import build_idempotency_request_hash, get_idempotency_key
from apps.core.models import IdempotencyRecord
from apps.core.services import idempotency_record_claim, idempotency_record_complete
from apps.links.metrics import short_link_redirects_total
from apps.links.models import ShortLink
from apps.links.selectors import (
    short_link_get_for_user,
    short_link_get_redirectable_by_code,
    short_link_list_for_user,
)
from apps.links.serializers import (
    ShortLinkCreateSerializer,
    ShortLinkListQuerySerializer,
    ShortLinkSerializer,
    ShortLinkUpdateSerializer,
)
from apps.links.services import short_link_create, short_link_delete, short_link_update
from config.api.pagination import DefaultPageNumberPagination

logger = structlog.getLogger()


class ShortLinkListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_throttles(self) -> list[BaseThrottle]:
        if self.request.method == "POST":
            self.throttle_scope = "short_link_create"
            return [ScopedRateThrottle()]
        return []

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        query_serializer = ShortLinkListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        links = short_link_list_for_user(
            user=user,
            is_active=query_serializer.validated_data.get("is_active"),
            search=query_serializer.validated_data.get("search"),
            ordering=query_serializer.validated_data.get("ordering"),
        )

        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(
            queryset=links,
            request=request,
            view=self,
        )

        serializer = ShortLinkSerializer(page, many=True)
        return paginator.get_paginated_response(
            data=serializer.data,
            message="Short links retrieved successfully",
        )

    def post(self, request: Request) -> Response:
        user = cast(User, request.user)

        serializer = ShortLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = get_idempotency_key(request=request)

        if idempotency_key is None:
            try:
                link = short_link_create(owner=user, **serializer.validated_data)
            except ValueError as exc:
                raise ValidationError({"short_code": str(exc)})
            except PlanLimitExceededError as exc:
                raise PermissionDenied(str(exc)) from exc

            response_serializer = ShortLinkSerializer(link)

            return Response(
                data=response_serializer.data, status=status.HTTP_201_CREATED
            )

        request_hash = build_idempotency_request_hash(
            data=dict(serializer.validated_data)
        )
        with transaction.atomic():
            claim = idempotency_record_claim(
                owner=user,
                key=idempotency_key,
                request_hash=request_hash,
            )

            if not claim.created:
                record = claim.record
                if record.request_hash != request_hash:
                    raise IdempotencyConflict()

                if record.status == IdempotencyRecord.Status.COMPLETED:
                    response = Response(
                        data=record.response_data, status=record.response_status
                    )
                    response["Idempotency-Replayed"] = "true"
                    return response

                raise IdempotencyConflict(
                    "A request with this idempotency key is already being processed"
                )

            try:
                short_link = short_link_create(owner=user, **serializer.validated_data)
            except ValueError as exc:
                raise ValidationError({"short_code": str(exc)})
            except PlanLimitExceededError as exc:
                raise PermissionDenied(str(exc)) from exc

            response_data = ShortLinkSerializer(short_link).data

            idempotency_record_complete(
                record=claim.record,
                response_status=status.HTTP_201_CREATED,
                response_data=dict(response_data),
                short_link=short_link,
            )
        return Response(response_data, status=status.HTTP_201_CREATED)


class ShortLinkDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_link(
        self,
        *,
        user: User,
        link_id: UUID,
    ) -> ShortLink:
        link = short_link_get_for_user(
            user=user,
            link_id=link_id,
        )

        if link is None:
            raise NotFound("Short link not found.")

        return link

    def get(self, request: Request, link_id: UUID) -> Response:
        user = cast(User, request.user)
        link = self.get_link(user=user, link_id=link_id)

        serializer = ShortLinkSerializer(link)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request, link_id: UUID) -> Response:
        user = cast(User, request.user)
        link = self.get_link(user=user, link_id=link_id)

        serializer = ShortLinkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expires_at_provided = "expires_at" in serializer.validated_data

        updated_link = short_link_update(
            link=link,
            **serializer.validated_data,
            update_expires_at=expires_at_provided,
        )
        response_serializer = ShortLinkSerializer(updated_link)

        return Response(data=response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request: Request, link_id: UUID):
        user = cast(User, request.user)
        link = self.get_link(user=user, link_id=link_id)

        short_link_delete(link=link)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ShortLinkRedirectAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request, short_code: str):
        link = short_link_get_redirectable_by_code(short_code=short_code)
        if link is None:
            short_link_redirects_total.labels(outcome="not_found").inc()
            raise NotFound("Short link not found.")

        short_link_redirects_total.labels(outcome="success").inc()
        try:
            click_event_create_task.delay(
                short_link_id=str(link.id),
                referrer=request.META.get("HTTP_REFERER", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip_address=get_client_ip(request=request),
            )
            click_event_dispatch_total.labels(outcome="success").inc()
        except Exception:  # noqa
            click_event_dispatch_total.labels(outcome="failure").inc()
            logger.exception(
                "click_event_dispatch_failed",
                short_link_id=str(link.id),
                destination_url=link.destination_url,
            )

        return redirect(to=link.destination_url, permanent=False)
