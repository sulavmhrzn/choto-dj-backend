from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.billing.models import (
    BillingCustomer,
    PaymentProvider,
    Plan,
    PlanCode,
    ProviderPlanPrice,
    ProviderSubscription,
    SubscriptionStatus,
)
from apps.billing.selectors import (
    subscription_get_for_user,
    subscription_get_for_user_for_update,
)
from apps.billing.services import (
    billing_checkout_session_create,
    billing_customer_get_or_create_stripe,
    provider_subscription_create,
    stripe_subscription_created_handle,
    stripe_subscription_deleted_handle,
    stripe_subscription_updated_handle,
    subscription_activate_plan,
    subscription_can_create_short_link,
    subscription_create_default,
)
from apps.billing.tests.conftest import build_stripe_subscription_event


@pytest.mark.django_db
def test_subscription_create_default_creates_free_subscription():
    user = User.objects.create_user(email="sulav@mail.com", password="sulavmhrzn")
    subscription = subscription_create_default(user=user)

    assert subscription.user == user
    assert subscription.plan.code == PlanCode.FREE
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.current_period_end is None
    assert subscription.current_period_start is None
    assert subscription.cancel_at_period_end is False


@pytest.mark.django_db
def test_subscription_create_default_fails_when_free_plan_is_inactive(user):
    Plan.objects.filter(code=PlanCode.FREE).update(is_active=False)

    with pytest.raises(RuntimeError, match="Active Free plan does not exist."):
        subscription_create_default(user=user)


@pytest.mark.django_db
def test_subscription_create_default_cannot_create_second_subscription():
    user = User.objects.create_user(email="sulav@mail.com", password="sulavmhrzn")

    subscription_create_default(
        user=user,
    )

    with pytest.raises(IntegrityError):
        subscription_create_default(
            user=user,
        )


@pytest.mark.django_db
def test_subscription_can_create_short_link_when_below_limit(user):
    subscription = subscription_get_for_user_for_update(user=user)

    result = subscription_can_create_short_link(
        subscription=subscription, current_short_link_count=49
    )

    assert result is True


@pytest.mark.django_db
def test_subscription_cannot_create_short_link_at_limit(user):
    subscription = subscription_get_for_user_for_update(user=user)

    result = subscription_can_create_short_link(
        subscription=subscription,
        current_short_link_count=50,
    )

    assert result is False


@pytest.mark.django_db
def test_billing_customer_get_or_create_stripe_creates_customer(user):
    with patch(
        "apps.billing.services.stripe_customer_create", return_value="cus_test123"
    ) as stripe_customer_create_mock:
        billing_customer = billing_customer_get_or_create_stripe(
            user=user,
        )

    assert billing_customer.user == user
    assert billing_customer.provider == PaymentProvider.STRIPE
    assert billing_customer.provider_customer_id == "cus_test123"

    stripe_customer_create_mock.assert_called_once()


@pytest.mark.django_db
def test_billing_customer_get_or_create_stripe_reuses_existing_customer(user):
    existing = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_existing",
    )

    with patch(
        "apps.billing.services.stripe_customer_create"
    ) as stripe_customer_create_mock:
        result = billing_customer_get_or_create_stripe(user=user)

    assert result == existing
    stripe_customer_create_mock.assert_not_called()


@pytest.mark.django_db
def test_billing_customer_get_or_create_stripe_retries_incomplete_customer(user):
    existing = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
    )

    with patch(
        "apps.billing.services.stripe_customer_create", return_value="cus_recovered"
    ) as stripe_customer_create_mock:
        result = billing_customer_get_or_create_stripe(user=user)

    assert result.id == existing.id
    assert result.provider_customer_id == "cus_recovered"
    stripe_customer_create_mock.assert_called_once_with(
        user=user, idempotency_key=f"billing-customer-{existing.id}"
    )


@pytest.mark.django_db
def test_subscription_create_default_assigns_free_plan(user):
    user.subscription.delete()

    subscription = subscription_create_default(user=user)

    assert subscription.plan.code == PlanCode.FREE
    assert subscription.user == user


@pytest.mark.django_db
def test_subscription_create_default_raises_when_free_plan_missing(user):
    user.subscription.delete()
    Plan.objects.filter(code=PlanCode.FREE).update(is_active=False)

    with pytest.raises(RuntimeError):
        subscription_create_default(user=user)


@pytest.mark.django_db
def test_billing_customer_get_or_create_stripe_creates_new(user):
    with patch(
        "apps.billing.services.stripe_customer_create", return_value="cus_new123"
    ) as mock_create:
        result = billing_customer_get_or_create_stripe(user=user)

    assert result.provider_customer_id == "cus_new123"
    assert result.user == user
    mock_create.assert_called_once()


@pytest.mark.django_db
def test_billing_customer_get_or_create_stripe_reuses_completed_customer(user):
    existing = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_already_done",
    )

    with patch("apps.billing.services.stripe_customer_create") as mock_create:
        result = billing_customer_get_or_create_stripe(user=user)

    assert result.id == existing.id
    mock_create.assert_not_called()


@pytest.mark.django_db
def test_provider_subscription_create_closes_previous_active_row(user):
    subscription = subscription_get_for_user(user=user)
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_1",
    )
    old = provider_subscription_create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_old",
    )
    new = provider_subscription_create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_new",
    )

    old.refresh_from_db()

    assert old.ended_at is not None
    assert new.ended_at is None
    assert ProviderSubscription.objects.filter(subscription=subscription).count() == 2


@pytest.mark.django_db
def test_provider_subscription_create_first_call_has_no_previous_to_close(user):
    subscription = subscription_get_for_user(user=user)
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_2",
    )

    result = provider_subscription_create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_first",
    )

    assert result.ended_at is None


@pytest.mark.django_db
def test_subscription_activate_plan_updates_all_fields(user):
    subscription = subscription_get_for_user(user=user)
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    period_start = timezone.now()
    period_end = period_start + timezone.timedelta(days=30)

    result = subscription_activate_plan(
        subscription=subscription,
        plan=pro_plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=period_start,
        current_period_end=period_end,
        cancel_at_period_end=True,
    )

    result.refresh_from_db()

    assert result.plan == pro_plan
    assert result.status == SubscriptionStatus.ACTIVE
    assert result.cancel_at_period_end is True
    assert result.current_period_end == period_end


@pytest.mark.django_db
def test_billing_checkout_session_create_blocks_resubscribe_to_same_plan(user, rf):
    subscription = subscription_get_for_user(user=user)
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    subscription.plan = pro_plan
    subscription.save(update_fields=["plan"])

    request = rf.post("/")

    with pytest.raises(ValidationError):
        billing_checkout_session_create(user=user, plan=pro_plan, request=request)


@pytest.mark.django_db
def test_billing_checkout_session_create_raises_when_price_not_configured(user, rf):
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    request = rf.post("/")

    with patch("apps.billing.services.stripe_customer_create", return_value="cus_x"):
        with pytest.raises(RuntimeError):
            billing_checkout_session_create(user=user, plan=pro_plan, request=request)


@pytest.mark.django_db
def test_billing_checkout_session_create_returns_stripe_url(user, rf):
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    ProviderPlanPrice.objects.create(
        plan=pro_plan, provider=PaymentProvider.STRIPE, provider_price_id="price_x"
    )
    request = rf.post("/")

    with (
        patch("apps.billing.services.stripe_customer_create", return_value="cus_x"),
        patch(
            "apps.billing.services.stripe_checkout_session_create",
            return_value="https://checkout.stripe.com/test_session",
        ) as mock_checkout,
    ):
        url = billing_checkout_session_create(user=user, plan=pro_plan, request=request)

    assert url == "https://checkout.stripe.com/test_session"
    mock_checkout.assert_called_once()
    call_kwargs = mock_checkout.call_args.kwargs
    assert call_kwargs["provider_customer_id"] == "cus_x"
    assert call_kwargs["provider_price_id"] == "price_x"


@pytest.mark.django_db
def test_stripe_subscription_created_handle_activates_plan(user):
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_test123",
    )
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    ProviderPlanPrice.objects.create(
        plan=pro_plan,
        provider=PaymentProvider.STRIPE,
        provider_price_id="price_test123",
    )

    event = build_stripe_subscription_event()
    stripe_subscription_created_handle(event=event)

    subscription = subscription_get_for_user(user=user)

    assert subscription.plan.code == PlanCode.PRO
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert ProviderSubscription.objects.filter(
        provider_subscription_id="sub_test123", billing_customer=billing_customer
    ).exists()


@pytest.mark.django_db
def test_stripe_subscription_created_handle_noop_when_billing_customer_unknown(user):
    event = build_stripe_subscription_event(customer="cus_never_seen")

    stripe_subscription_created_handle(event=event)

    subscription = subscription_get_for_user(user=user)

    assert subscription.plan.code == PlanCode.FREE
    assert ProviderSubscription.objects.count() == 0


@pytest.mark.django_db
def test_stripe_subscription_updated_handle_refreshes_data(user):
    subscription = subscription_get_for_user(user=user)
    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_test123",
    )
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    ProviderPlanPrice.objects.create(
        plan=pro_plan,
        provider=PaymentProvider.STRIPE,
        provider_price_id="price_test123",
    )
    ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_test123",
    )
    event = build_stripe_subscription_event(current_period_end=1800000000)

    stripe_subscription_updated_handle(event=event)

    subscription.refresh_from_db()
    assert subscription.plan.code == PlanCode.PRO
    assert subscription.current_period_end.timestamp() == 1800000000


@pytest.mark.django_db
def test_stripe_subscription_deleted_handle_downgrades_to_free(user):
    subscription = subscription_get_for_user(user=user)
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    subscription.plan = pro_plan
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.save(update_fields=["plan", "status"])

    billing_customer = BillingCustomer.objects.create(
        user=user,
        provider=PaymentProvider.STRIPE,
        provider_customer_id="cus_test123",
    )

    provider_subscription = ProviderSubscription.objects.create(
        subscription=subscription,
        billing_customer=billing_customer,
        provider_subscription_id="sub_test123",
    )

    event = build_stripe_subscription_event(ended_at=1750000000)

    stripe_subscription_deleted_handle(event=event)

    subscription.refresh_from_db()
    provider_subscription.refresh_from_db()

    assert subscription.plan.code == PlanCode.FREE
    assert subscription.status == SubscriptionStatus.CANCELED
    assert subscription.current_period_start is None
    assert provider_subscription.ended_at is not None


@pytest.mark.django_db
def test_stripe_subscription_deleted_handle_noop_when_unknown(user):
    subscription = subscription_get_for_user(user=user)
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    subscription.plan = pro_plan
    subscription.save(update_fields=["plan"])

    event = build_stripe_subscription_event(id="sub_never_seen")

    stripe_subscription_deleted_handle(event=event)

    subscription.refresh_from_db()
    assert subscription.plan.code == PlanCode.PRO
