import logging
from typing import cast
from uuid import UUID

from django.shortcuts import redirect
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.analytics.services import click_event_create
from apps.analytics.tasks import click_event_create_task
from apps.analytics.utils import get_client_ip
from apps.links.models import ShortLink
from apps.links.selectors import (
    short_link_get_for_user,
    short_link_get_redirectable_by_code,
    short_link_list_for_user,
)
from apps.links.serializers import (
    ShortLinkCreateSerializer,
    ShortLinkSerializer,
    ShortLinkUpdateSerializer,
)
from apps.links.services import short_link_create, short_link_delete, short_link_update

logger = logging.getLogger(__name__)


class ShortLinkListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        links = short_link_list_for_user(user=user)
        serializer = ShortLinkSerializer(links, many=True)

        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        user = cast(User, request.user)

        serializer = ShortLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            link = short_link_create(owner=user, **serializer.validated_data)
        except ValueError as exc:
            raise ValidationError({"short_code": str(exc)})

        response_serializer = ShortLinkSerializer(link)

        return Response(data=response_serializer.data, status=status.HTTP_201_CREATED)


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
            raise NotFound("Short link not found.")

        try:
            click_event_create_task.delay(
                short_link_id=str(link.id),
                referrer=request.META.get("HTTP_REFERER", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ip_address=get_client_ip(request=request),
            )
        except Exception:  # noqa
            logger.exception(
                "Failed to dispatch click event task for short link %s.",
                link.id,
                exc_info=True,
            )

        return redirect(to=link.destination_url, permanent=False)
