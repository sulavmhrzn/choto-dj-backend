import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import (
    BillingCustomer,
    PaymentProvider,
    Plan,
    PlanCode,
    ProviderPlanPrice,
    ProviderSubscription,
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


@pytest.mark.django_db
def test_subscription_get_for_user_return_subscription(user):

    subscription = user.subscription

    result = subscription_get_for_user(user=user)

    assert result == subscription
    assert result.plan.code == PlanCode.FREE


@pytest.mark.django_db
def test_subscription_get_for_user_returns_none_when_missing():
    user = User.objects.create_user(
        email="no-subscription@example.com",
    )

    result = subscription_get_for_user(
        user=user,
    )

    assert result is None


@pytest.mark.django_db
def test_subscription_get_for_user_loads_plan(user, django_assert_num_queries):

    with django_assert_num_queries(1):
        subscription = subscription_get_for_user(user=user)

        assert subscription is not None
        assert subscription.plan.code == PlanCode.FREE


@pytest.mark.django_db
def test_plan_get_by_code_returns_active_plan():
    plan = Plan.objects.get(code=PlanCode.PRO)

    result = plan_get_by_code(code=PlanCode.PRO)

    assert result == plan


@pytest.mark.django_db
def test_plan_get_by_code_returns_none_for_inactive_plan():
    plan = Plan.objects.get(code=PlanCode.PRO)
    plan.is_active = False
    plan.save(update_fields=["is_active"])

    result = plan_get_by_code(code=PlanCode.PRO)

    assert result is None


@pytest.mark.django_db
def test_billing_customer_get_for_user_returns_matching_row(user):
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_123",
    )

    result = billing_customer_get_for_user(user=user, provider=PaymentProvider.STRIPE)

    assert result == billing_customer


@pytest.mark.django_db
def test_billing_customer_get_for_user_returns_none_when_missing(user):
    result = billing_customer_get_for_user(user=user, provider=PaymentProvider.STRIPE)

    assert result is None


@pytest.mark.django_db
def test_billing_customer_get_by_provider_customer_id_loads_user(
    user, django_assert_num_queries
):
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_456",
    )

    with django_assert_num_queries(1):
        result = billing_customer_get_by_provider_customer_id(
            provider_customer_id="cus_456"
        )
        assert result.id == billing_customer.id
        assert result.user == user


@pytest.mark.django_db
def test_billing_customer_get_by_provider_customer_id_returns_none_when_missing():
    result = billing_customer_get_by_provider_customer_id(
        provider_customer_id="cus_does_not_exist"
    )

    assert result is None


@pytest.mark.django_db
def test_provider_subscription_get_by_provider_id_loads_relations(
    user, django_assert_num_queries
):
    subscription = subscription_get_for_user(user=user)
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_789",
    )
    provider_subscription = ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_123",
    )

    with django_assert_num_queries(1):
        result = provider_subscription_get_by_provider_id(
            provider_subscription_id="sub_123"
        )

        assert result.id == provider_subscription.id
        assert result.subscription == subscription
        assert result.billing_customer == billing_customer


@pytest.mark.django_db
def test_provider_subscription_get_by_provider_id_returns_none_when_missing():
    result = provider_subscription_get_by_provider_id(
        provider_subscription_id="sub_does_not_exist"
    )

    assert result is None


@pytest.mark.django_db
def test_provider_subscription_get_active_for_subscription_ignores_ended_rows(user):
    subscription = subscription_get_for_user(user=user)
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_active",
    )
    ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_ended",
        ended_at=timezone.now(),
    )
    active = ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_active",
    )

    result = provider_subscription_get_active_for_subscription(
        subscription=subscription
    )

    assert result.id == active.id


@pytest.mark.django_db
def test_provider_subscription_get_active_for_subscription_returns_none_when_all_ended(
    user,
):
    subscription = subscription_get_for_user(user=user)
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_none_active",
    )
    ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_ended_only",
        ended_at=timezone.now(),
    )

    result = provider_subscription_get_active_for_subscription(
        subscription=subscription
    )

    assert result is None


@pytest.mark.django_db
def test_provider_plan_price_get_by_provider_price_id_loads_plan(
    django_assert_num_queries,
):
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    provider_plan_price = ProviderPlanPrice.objects.create(
        plan=pro_plan,
        provider=PaymentProvider.STRIPE,
        provider_price_id="price_test123",
    )

    with django_assert_num_queries(1):
        result = provider_plan_price_get_by_provider_price_id(
            provider_price_id="price_test123"
        )

        assert result.id == provider_plan_price.id
        assert result.plan == pro_plan


@pytest.mark.django_db
def test_provider_plan_price_get_by_provider_price_id_returns_none_when_missing():
    result = provider_plan_price_get_by_provider_price_id(
        provider_price_id="price_does_not_exist"
    )

    assert result is None


@pytest.mark.django_db
def test_provider_plan_price_get_for_plan_returns_matching_row():
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    provider_plan_price = ProviderPlanPrice.objects.create(
        plan=pro_plan,
        provider=PaymentProvider.STRIPE,
        provider_price_id="price_outbound",
    )

    result = provider_plan_price_get_for_plan(
        plan=pro_plan, provider=PaymentProvider.STRIPE
    )

    assert result == provider_plan_price


@pytest.mark.django_db
def test_provider_plan_price_get_for_plan_returns_none_when_missing():
    pro_plan = Plan.objects.get(code=PlanCode.PRO)

    result = provider_plan_price_get_for_plan(
        plan=pro_plan, provider=PaymentProvider.STRIPE
    )

    assert result is None
