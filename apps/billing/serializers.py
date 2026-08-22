from rest_framework import serializers

from apps.billing.models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "code",
            "name",
            "price_monthly",
            "short_link_limit",
            "webhook_endpoint_limit",
            "analytics_retention_days",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
