from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import User
from apps.billing.models import (
    PaymentProvider,
    Plan,
    PlanCode,
    ProviderPlanPrice,
    SubscriptionStatus,
)
from apps.billing.selectors import subscription_get_for_user


@pytest.mark.django_db
def test_subscription_detail_returns_current_subscription(authenticated_client):
    response = authenticated_client.get(reverse("billing:subscription-detail"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == SubscriptionStatus.ACTIVE
    assert response.data["plan"]["code"] == PlanCode.FREE
    assert response.data["plan"]["name"] == "Free"
    assert response.data["plan"]["short_link_limit"] == 50


@pytest.mark.django_db
def test_subscription_detail_returns_plan_entitlements(
    authenticated_client,
):
    response = authenticated_client.get(
        reverse("billing:subscription-detail"),
    )

    assert response.status_code == status.HTTP_200_OK

    plan = response.data["plan"]

    assert set(plan.keys()) == {
        "code",
        "name",
        "price_monthly",
        "short_link_limit",
        "webhook_endpoint_limit",
        "analytics_retention_days",
    }


@pytest.mark.django_db
def test_subscription_detail_requires_authentication(
    api_client,
):
    response = api_client.get(
        reverse("billing:subscription-detail"),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_subscription_detail_returns_server_error_when_subscription_missing(
    api_client,
):
    user = User.objects.create_user(
        email="broken@example.com",
        password="password123",
    )

    api_client.force_authenticate(user=user)

    response = api_client.get(
        reverse("billing:subscription-detail"),
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.django_db
def test_checkout_create_returns_url_for_valid_plan(authenticated_client, user):
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    ProviderPlanPrice.objects.create(
        plan=pro_plan, provider=PaymentProvider.STRIPE, provider_price_id="price_x"
    )

    with (
        patch("apps.billing.services.stripe_customer_create", return_value="cus_x"),
        patch(
            "apps.billing.services.stripe_checkout_session_create",
            return_value="https://checkout.stripe.com/test_session",
        ),
    ):
        response = authenticated_client.post(
            reverse("billing:checkout-create"), {"plan_code": "pro"}
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["checkout_url"] == "https://checkout.stripe.com/test_session"


@pytest.mark.django_db
def test_checkout_create_rejects_invalid_plan_code(authenticated_client, user):
    response = authenticated_client.post(
        reverse("billing:checkout-create"), {"plan_code": "not_a_real_plan"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "plan_code" in response.data["errors"]


@pytest.mark.django_db
def test_checkout_create_rejects_missing_plan_code(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("billing:checkout-create"), {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_checkout_create_blocks_resubscribe_to_current_plan(authenticated_client, user):
    subscription = subscription_get_for_user(user=user)
    pro_plan = Plan.objects.get(code=PlanCode.PRO)
    subscription.plan = pro_plan
    subscription.save(update_fields=["plan"])
    ProviderPlanPrice.objects.create(
        plan=pro_plan, provider=PaymentProvider.STRIPE, provider_price_id="price_x"
    )

    response = authenticated_client.post(
        reverse("billing:checkout-create"), {"plan_code": "pro"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_checkout_create_requires_authentication(api_client):
    response = api_client.post(
        reverse("billing:checkout-create"),
        {"plan_code": "pro"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_stripe_webhook_returns_400_on_invalid_signature(api_client):
    with patch(
        "apps.billing.views.stripe_webhook_event_construct",
        side_effect=Exception("bad signature"),
    ):
        response = api_client.post(
            reverse("billing:stripe-webhook"),
            data=b'{"type": "irrelevant"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad_sig",
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_stripe_webhook_returns_200_and_ignores_unrouted_event_type(api_client):
    fake_event = type("Event", (), {"type": "charge.succeeded"})()

    with patch(
        "apps.billing.views.stripe_webhook_event_construct", return_value=fake_event
    ):
        response = api_client.post(
            reverse("billing:stripe-webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_sig",
        )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_stripe_webhook_routes_subscription_created_to_handler(api_client):
    fake_event = type("Event", (), {"type": "customer.subscription.created"})()

    with (
        patch(
            "apps.billing.views.stripe_webhook_event_construct", return_value=fake_event
        ),
        patch("apps.billing.views.stripe_subscription_created_handle") as mock_handler,
    ):
        response = api_client.post(
            reverse("billing:stripe-webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_si",
        )

    assert response.status_code == status.HTTP_200_OK
    mock_handler.assert_called_once_with(event=fake_event)


@pytest.mark.django_db
def test_stripe_webhook_does_not_require_authentication(api_client):
    with patch(
        "apps.billing.views.stripe_webhook_event_construct",
        side_effect=Exception("bad"),
    ):
        response = api_client.post(
            reverse("billing:stripe-webhook"),
            data=b"{}",
            content_type="application/json",
        )

    assert response.status_code != status.HTTP_401_UNAUTHORIZED
