from rest_framework import serializers

from apps.webhooks.models import WebhookEndpoint, WebhookEventType


class WebhookEndpointCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    url = serializers.URLField(max_length=500)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=WebhookEventType.choices),
        allow_empty=False,
    )

    def validate_events(self, value) -> list[str]:
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Webhook events must be unique.")
        return value


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "name",
            "url",
            "events",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WebhookEndpointUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    url = serializers.URLField(max_length=500, required=False)
    events = serializers.ListField(
        child=serializers.ChoiceField(WebhookEventType.choices),
        allow_empty=False,
        required=False,
    )
    is_active = serializers.BooleanField(required=False)

    def validate_events(self, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Webhook events must be unique.")
        return value
