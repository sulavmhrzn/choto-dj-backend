import uuid

from django.conf import settings
from django.db import models


class PlanCode(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past due"
    CANCELED = "canceled", "Canceled"


class PaymentProvider(models.TextChoices):
    STRIPE = "stripe", "Stripe"


class Plan(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(
        max_length=20,
        choices=PlanCode.choices,
        unique=True,
    )
    name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)

    short_link_limit = models.PositiveIntegerField()
    webhook_endpoint_limit = models.PositiveIntegerField()
    analytics_retention_days = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
    )

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user} -> {self.plan.name}"


class BillingCustomer(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_customers",
    )

    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    provider_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="unique_billing_customer_per_user_provider",
            ),
            models.UniqueConstraint(
                fields=["provider", "provider_customer_id"],
                name="unique_provider_customer_id",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.provider}"


class ProviderSubscription(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="provider_subscriptions",
    )

    billing_customer = models.ForeignKey(
        BillingCustomer,
        on_delete=models.PROTECT,
        related_name="provider_subscriptions",
    )

    provider_subscription_id = models.CharField(max_length=255, unique=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.provider_subscription_id


class ProviderPlanPrice(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="provider_prices",
    )

    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    provider_price_id = models.CharField(max_length=255, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "provider"],
                name="unique_active_price_per_plan_provider",
            )
        ]

    def __str__(self):
        return f"{self.plan.code} -> {self.provider_price_id}"
