from apps.accounts.models import User
from apps.billing.models import (
    BillingCustomer,
    PaymentProvider,
    Plan,
    PlanCode,
    ProviderPlanPrice,
    ProviderSubscription,
    Subscription,
)


def plan_get_by_code(*, code: PlanCode) -> Plan | None:
    return Plan.objects.filter(
        code=code,
        is_active=True,
    ).first()


def subscription_get_for_user(*, user: User) -> Subscription | None:
    return Subscription.objects.select_related("plan").filter(user=user).first()


def subscription_get_for_user_for_update(*, user: User) -> Subscription | None:
    return (
        Subscription.objects.select_for_update()
        .select_related("plan")
        .filter(user=user)
        .first()
    )


def billing_customer_get_for_user(
    *, user: User, provider: PaymentProvider
) -> BillingCustomer | None:
    return BillingCustomer.objects.filter(user=user, provider=provider).first()


def provider_subscription_get_by_provider_id(
    *, provider_subscription_id: str
) -> ProviderSubscription | None:
    return (
        ProviderSubscription.objects.select_related("subscription", "billing_customer")
        .filter(provider_subscription_id=provider_subscription_id)
        .first()
    )


def provider_subscription_get_active_for_subscription(
    *, subscription: Subscription
) -> ProviderSubscription | None:
    return ProviderSubscription.objects.filter(
        subscription=subscription, ended_at__isnull=True
    ).first()


def provider_plan_price_get_by_provider_price_id(
    *, provider_price_id: str
) -> ProviderPlanPrice | None:
    return (
        ProviderPlanPrice.objects.select_related("plan")
        .filter(provider_price_id=provider_price_id)
        .first()
    )


def provider_plan_price_get_for_plan(*, plan: Plan, provider: PaymentProvider):
    return ProviderPlanPrice.objects.filter(plan=plan, provider=provider).first()


def billing_customer_get_by_provider_customer_id(
    *, provider_customer_id: str
) -> BillingCustomer | None:
    return (
        BillingCustomer.objects.select_related("user")
        .filter(provider_customer_id=provider_customer_id)
        .first()
    )
