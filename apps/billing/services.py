import uuid
from datetime import datetime
from datetime import timezone as dt_timezone

import stripe
import structlog
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from stripe import Plan

from apps.accounts.models import User
from apps.billing.models import (
    BillingCustomer,
    PaymentProvider,
    PlanCode,
    ProviderSubscription,
    Subscription,
    SubscriptionStatus,
)
from apps.billing.providers.stripe import (
    stripe_checkout_session_create,
    stripe_customer_create,
)
from apps.billing.selectors import (
    billing_customer_get_by_provider_customer_id,
    billing_customer_get_for_user,
    plan_get_by_code,
    provider_plan_price_get_by_provider_price_id,
    provider_plan_price_get_for_plan,
    provider_subscription_get_active_for_subscription,
    provider_subscription_get_by_provider_id,
    subscription_get_for_user,
)

logger = structlog.getLogger()


def subscription_create_default(*, user: User) -> Subscription:
    free_plan = plan_get_by_code(code=PlanCode.FREE)

    if free_plan is None:
        raise RuntimeError("Active Free plan does not exist.")

    return Subscription.objects.create(user=user, plan=free_plan)


def subscription_can_create_short_link(
    *, subscription: Subscription, current_short_link_count: int
) -> bool:
    return current_short_link_count < subscription.plan.short_link_limit


@transaction.atomic
def billing_customer_get_or_create_stripe(*, user: User) -> BillingCustomer:
    billing_customer = billing_customer_get_for_user(
        user=user, provider=PaymentProvider.STRIPE
    )

    if (
        billing_customer is not None
        and billing_customer.provider_customer_id is not None
    ):
        return billing_customer

    if billing_customer is None:
        billing_customer = BillingCustomer.objects.create(
            user=user,
            provider=PaymentProvider.STRIPE,
        )

    provider_customer_id = stripe_customer_create(
        user=user, idempotency_key=f"billing-customer-{billing_customer.id}"
    )

    billing_customer.provider_customer_id = provider_customer_id
    billing_customer.save(update_fields=["provider_customer_id", "updated_at"])

    return billing_customer


@transaction.atomic
def provider_subscription_create(
    *,
    subscription: Subscription,
    billing_customer: BillingCustomer,
    provider_subscription_id: str,
) -> ProviderSubscription:
    existing_active = provider_subscription_get_active_for_subscription(
        subscription=subscription
    )

    if existing_active is not None:
        existing_active.ended_at = timezone.now()
        existing_active.save(update_fields=["ended_at", "updated_at"])

    return ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id=provider_subscription_id,
    )


def subscription_activate_plan(
    *,
    subscription: Subscription,
    plan: Plan,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
    cancel_at_period_end: bool = False,
) -> Subscription:
    subscription.plan = plan
    subscription.status = status
    subscription.current_period_start = current_period_start
    subscription.current_period_end = current_period_end
    subscription.cancel_at_period_end = cancel_at_period_end

    subscription.save(
        update_fields=[
            "plan",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "updated_at",
        ]
    )
    return subscription


def billing_checkout_session_create(*, user: User, plan: Plan, request) -> str:
    subscription = subscription_get_for_user(user=user)

    if subscription is not None and subscription.plan_id == plan.id:
        if subscription.status == SubscriptionStatus.PAST_DUE:
            raise ValidationError(
                {
                    "plan_code": (
                        "Your Pro subscription has a payment issue. "
                        "Please update your payment method instead of checking out again."
                    )
                }
            )
        raise ValidationError({"plan_code": "You are already subscribed to this plan."})

    billing_customer = billing_customer_get_or_create_stripe(user=user)

    provider_plan_price = provider_plan_price_get_for_plan(
        plan=plan, provider=PaymentProvider.STRIPE
    )

    if provider_plan_price is None:
        raise RuntimeError(f"No Stripe price configured for plan '{plan.code}'")

    success_url = (
        request.build_absolute_uri(reverse("billing:checkout-success"))
        + "?session_id={CHECKOUT_SESSION_ID}"
    )

    cancel_url = request.build_absolute_uri(reverse("billing:checkout-cancel"))

    checkout_url = stripe_checkout_session_create(
        provider_customer_id=billing_customer.provider_customer_id,
        provider_price_id=provider_plan_price.provider_price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=f"checkout-{uuid.uuid4()}",
    )

    return checkout_url


def _stripe_timestamp_to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)


def stripe_subscription_created_handle(event: stripe.Event) -> None:
    stripe_subscription = event.data.object

    billing_customer = billing_customer_get_by_provider_customer_id(
        provider_customer_id=stripe_subscription["customer"]
    )
    if billing_customer is None:
        logger.warning(
            "stripe_webhook_unknown_billing_customer",
            provider_customer_id=stripe_subscription["customer"],
        )
        return

    subscription = subscription_get_for_user(user=billing_customer.user)

    if subscription is None:
        logger.warning(
            "stripe_webhook_no_local_subscription",
            user_id=str(billing_customer.user_id),
        )
        return

    price_id = stripe_subscription["items"]["data"][0]["price"]["id"]

    provider_plan_price = provider_plan_price_get_by_provider_price_id(
        provider_price_id=price_id
    )
    if provider_plan_price is None:
        logger.warning(
            "stripe_webhook_unknown_provider_price", provider_price_id=price_id
        )
        return

    provider_subscription_create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id=stripe_subscription["id"],
    )

    subscription_activate_plan(
        subscription=subscription,
        plan=provider_plan_price.plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=_stripe_timestamp_to_datetime(
            stripe_subscription["current_period_start"]
        ),
        current_period_end=_stripe_timestamp_to_datetime(
            stripe_subscription["current_period_end"]
        ),
        cancel_at_period_end=stripe_subscription["cancel_at_period_end"],
    )


def stripe_subscription_updated_handle(event: stripe.Event) -> None:
    stripe_subscription = event.data.object

    provider_subscription = provider_subscription_get_by_provider_id(
        provider_subscription_id=stripe_subscription["id"]
    )

    if provider_subscription is None:
        logger.warning(
            "stripe_webhook_unknown_provider_subscription",
            provider_subscription_id=stripe_subscription["id"],
        )
        return

    price_id = stripe_subscription["items"]["data"][0]["price"]["id"]

    provider_plan_price = provider_plan_price_get_by_provider_price_id(
        provider_price_id=price_id
    )

    if provider_plan_price is None:
        logger.warning(
            "stripe_webhook_unknown_provider_price", provider_price_id=price_id
        )
        return

    subscription_activate_plan(
        subscription=provider_subscription.subscription,
        plan=provider_plan_price.plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=_stripe_timestamp_to_datetime(
            stripe_subscription["current_period_start"]
        ),
        current_period_end=_stripe_timestamp_to_datetime(
            stripe_subscription["current_period_end"]
        ),
        cancel_at_period_end=stripe_subscription["cancel_at_period_end"],
    )


def stripe_subscription_deleted_handle(*, event: stripe.Event) -> None:
    stripe_subscription = event.data.object

    provider_subscription = provider_subscription_get_by_provider_id(
        provider_subscription_id=stripe_subscription["id"]
    )

    if provider_subscription is None:
        logger.warning(
            "stripe_webhook_unknown_provider_subscription",
            provider_subscription_id=stripe_subscription["id"],
        )
        return

    ended_at = _stripe_timestamp_to_datetime(
        timestamp=getattr(stripe_subscription, "ended_at", None)
    )

    provider_subscription.ended_at = ended_at or timezone.now()
    provider_subscription.save(update_fields=["ended_at", "updated_at"])

    free_plan = plan_get_by_code(code=PlanCode.FREE)

    if free_plan is None:
        logger.warning("stripe_webhook_free_plan_missing")
        return

    subscription_activate_plan(
        subscription=provider_subscription.subscription,
        plan=free_plan,
        status=SubscriptionStatus.CANCELED,
        current_period_start=None,
        current_period_end=None,
        cancel_at_period_end=False,
    )


def subscription_update_status(
    *, subscription: Subscription, status: SubscriptionStatus
) -> Subscription:
    subscription.status = status
    subscription.save(update_fields=["status", "updated_at"])
    return subscription


def stripe_invoice_payment_failed_handle(*, event: stripe.Event) -> None:
    invoice = event.data.object

    provider_subscription_id = getattr(invoice, "subscription", None)

    if provider_subscription_id is None:
        logger.info("stripe_webhook_invoice_not_subscription_related")
        return

    provider_subscription = provider_subscription_get_by_provider_id(
        provider_subscription_id=provider_subscription_id
    )

    if provider_subscription is None:
        logger.warning(
            "stripe_webhook_unknown_provider_subscription",
            provider_subscription_id=provider_subscription_id,
        )
        return

    subscription_update_status(
        subscription=provider_subscription.subscription,
        status=SubscriptionStatus.PAST_DUE,
    )
