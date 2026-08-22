import stripe
import structlog
from django.conf import settings

from apps.accounts.models import User

logger = structlog.getLogger()


def stripe_customer_create(*, user: User, idempotency_key: str) -> str:
    client = stripe.StripeClient(api_key=settings.STRIPE_SECRET_KEY)

    customer = client.v1.customers.create(
        params={
            "email": user.email,
            "name": user.full_name or None,
            "metadata": {
                "choto_user_id": str(user.id),
            },
        },
        options={
            "idempotency_key": idempotency_key,
        },
    )
    return customer.id


def stripe_webhook_event_construct(
    *, payload: bytes, signature_header: str
) -> stripe.Event:
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature_header,
        secret=settings.STRIPE_WEBHOOK_SECRET,
    )


def stripe_checkout_session_create(
    *,
    provider_customer_id: str,
    provider_price_id: str,
    success_url: str,
    cancel_url: str,
    idempotency_key: str,
) -> str:
    client = stripe.StripeClient(api_key=settings.STRIPE_SECRET_KEY)

    session = client.v1.checkout.sessions.create(
        params={
            "mode": "subscription",
            "customer": provider_customer_id,
            "line_items": [
                {
                    "price": provider_price_id,
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
        },
        options={
            "idempotency_key": idempotency_key,
        },
    )
    return session.url
