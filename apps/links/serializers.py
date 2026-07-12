from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.links.models import ShortLink


class ShortLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShortLink
        fields = (
            "id",
            "short_code",
            "destination_url",
            "title",
            "is_active",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ShortLinkCreateSerializer(serializers.Serializer):
    destination_url = serializers.URLField(max_length=2048)
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value


class ShortLinkUpdateSerializer(serializers.Serializer):
    destination_url = serializers.URLField(
        required=False,
        max_length=2048,
    )

    title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )

    is_active = serializers.BooleanField(
        required=False,
    )

    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("At least one field is required.")

        return attrs
