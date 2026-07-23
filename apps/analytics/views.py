from datetime import datetime, time, timedelta
from typing import cast
from uuid import UUID

import structlog
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.analytics.selectors import (
    click_event_get_daily_counts,
    click_event_recent_for_link,
    click_event_summary_for_link,
)
from apps.analytics.serializers import ClickEventSerializer
from apps.analytics.services import build_daily_click_counts
from apps.links.models import ShortLink
from apps.links.selectors import short_link_get_for_user

logger = structlog.getLogger()


class ShortLinkAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_short_link_or_404(self, *, user: User, link_id: UUID) -> ShortLink:
        link = short_link_get_for_user(user=user, link_id=link_id)
        if link is None:
            raise NotFound("Short link not found")

        return link

    def get(self, request: Request, link_id: UUID) -> Response:
        user = cast(User, request.user)
        link = self._get_short_link_or_404(user=user, link_id=link_id)

        today = timezone.localdate()
        start_of_today = timezone.make_aware(
            datetime.combine(today, time.min),
        )

        start_date = today - timedelta(days=29)
        start_at = timezone.make_aware(datetime.combine(start_date, time.min))

        summary = click_event_summary_for_link(
            short_link=link,
            since=start_of_today,
        )
        recent_clicks = click_event_recent_for_link(
            short_link=link,
            limit=20,
        )
        daily_counts = list(
            click_event_get_daily_counts(short_link=link, start_at=start_at)
        )
        clicks_over_time = build_daily_click_counts(
            start_date=start_date, end_date=today, counts=daily_counts
        )

        return Response(
            data={
                "total_clicks": summary["total_clicks"],
                "clicks_today": summary["clicks_since"],
                "unique_visitors": summary["unique_visitors"],
                "first_clicked_at": summary["first_clicked_at"],
                "last_clicked_at": summary["last_clicked_at"],
                "recent_clicks": ClickEventSerializer(
                    recent_clicks,
                    many=True,
                ).data,
                "clicks_over_time": clicks_over_time,
            },
            status=status.HTTP_200_OK,
        )
