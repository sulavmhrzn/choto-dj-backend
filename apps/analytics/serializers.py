from rest_framework import serializers

from apps.analytics.models import ClickEvent


class ClickEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickEvent
        fields = (
            "id",
            "clicked_at",
            "referrer",
            "user_agent",
            "ip_address",
        )
        read_only_fields = fields
