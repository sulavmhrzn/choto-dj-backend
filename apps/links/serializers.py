from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import APIKey
from apps.links.constants import (
    MAX_SHORT_CODE_LENGTH,
    MIN_SHORT_CODE_LENGTH,
    SHORT_LINK_ORDERING_CHOICES,
)
from apps.links.models import ShortLink
from apps.links.validators import is_reserved_short_code


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
    short_code = serializers.RegexField(
        regex=r"^[a-zA-Z0-9_-]+$",
        required=False,
        allow_blank=True,
        min_length=MIN_SHORT_CODE_LENGTH,
        max_length=MAX_SHORT_CODE_LENGTH,
        error_messages={
            "invalid": (
                "Custom alias may contain only letters, numbers, "
                "hyphens, and underscores."
            ),
        },
    )

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value

    def validate_short_code(self, value: str) -> str:
        short_code = value.strip().lower()

        if is_reserved_short_code(short_code=short_code):
            raise serializers.ValidationError("This custom alias is reserved.")

        return short_code


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


class ShortLinkListQuerySerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False, default=True)
    search = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    ordering = serializers.ChoiceField(
        required=False,
        default="-created_at",
        choices=SHORT_LINK_ORDERING_CHOICES,
    )

    def validate_search(self, value: str) -> str:
        return value.strip()


class APIKeyCreateSerailizer(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("API key name cannot be empty")

        return value


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "prefix",
            "is_active",
            "last_used_at",
            "created_at",
            "revoked_at",
        ]
        read_only_fields = fields
