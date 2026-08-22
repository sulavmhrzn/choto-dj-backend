from django.urls import path

from apps.billing.views import (
    CheckoutCancelView,
    CheckoutSessionCreateAPIView,
    CheckoutSuccessView,
    StripeWebhookAPIView,
    SubscriptionDetailAPIView,
)

app_name = "billing"

urlpatterns = [
    path(
        "subscription/",
        SubscriptionDetailAPIView.as_view(),
        name="subscription-detail",
    ),
    path(
        "webhooks/stripe/",
        StripeWebhookAPIView.as_view(),
        name="stripe-webhook",
    ),
    path(
        "checkout/success/",
        CheckoutSuccessView.as_view(),
        name="checkout-success",
    ),
    path(
        "checkout/cancel/",
        CheckoutCancelView.as_view(),
        name="checkout-cancel",
    ),
    path(
        "checkout/",
        CheckoutSessionCreateAPIView.as_view(),
        name="checkout-create",
    ),
]
