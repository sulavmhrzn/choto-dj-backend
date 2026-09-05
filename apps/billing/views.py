import structlog
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import PlanCode
from apps.billing.providers.stripe import stripe_webhook_event_construct
from apps.billing.selectors import (
    plan_get_by_code,
    subscription_get_for_user,
)
from apps.billing.serializers import SubscriptionSerializer
from apps.billing.services import (
    billing_checkout_session_create,
    stripe_invoice_payment_failed_handle,
    stripe_subscription_created_handle,
    stripe_subscription_deleted_handle,
    stripe_subscription_updated_handle,
)

logger = structlog.getLogger()


class CheckoutSuccessView(TemplateView):
    template_name = "billing/checkout_success.html"


class CheckoutCancelView(TemplateView):
    template_name = "billing/checkout_cancel.html"


class SubscriptionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Billing"], responses=SubscriptionSerializer)
    def get(self, request: Request) -> Response:
        subscription = subscription_get_for_user(user=request.user)

        if subscription is None:
            raise APIException("Subscription does not exist for this user.")

        serializer = SubscriptionSerializer(subscription)

        return Response(serializer.data)


class CheckoutSessionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Billing"],
        request=inline_serializer(
            name="CheckoutSessionCreateRequest",
            fields={"plan_code": serializers.ChoiceField(choices=PlanCode.choices)},
        ),
        responses=inline_serializer(
            name="CheckoutSessionCreateResponse",
            fields={"checkout_url": serializers.URLField()},
        ),
    )
    def post(self, request: Request) -> Response:
        plan_code = request.data.get("plan_code")

        if plan_code not in PlanCode.values:
            raise ValidationError({"plan_code": "Invalid or missing plan code"})

        plan = plan_get_by_code(code=plan_code)

        if plan is None:
            raise APIException("Requested plan is not currently available.")

        checkout_url = billing_checkout_session_create(
            user=request.user,
            plan=plan,
            request=request,
        )

        return Response({"checkout_url": checkout_url})


@extend_schema(exclude=True)
class StripeWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        signature_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe_webhook_event_construct(
                payload=request.body, signature_header=signature_header
            )
        except Exception:
            logger.warning("stripe_webhook_signature_verification_failed")
            return Response(status=400)

        logger.info("stripe_webhook_event_received", event_type=event.type)

        if event.type == "customer.subscription.created":
            stripe_subscription_created_handle(event=event)
        elif event.type == "customer.subscription.updated":
            stripe_subscription_updated_handle(event=event)
        elif event.type == "customer.subscription.deleted":
            stripe_subscription_deleted_handle(event=event)
        elif event.type == "invoice.payment_failed":
            stripe_invoice_payment_failed_handle(event=event)
        return Response(status=200)
