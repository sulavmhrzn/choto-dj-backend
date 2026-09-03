import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.services import user_create
from apps.billing.models import PlanCode
from apps.billing.selectors import plan_get_by_code, subscription_get_for_user
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEventType
from apps.webhooks.services import webhook_endpoint_create


@pytest.fixture
def user() -> User:
    user = user_create(
        email="sulav@mail.com",
        password="sulavmhrzn",
    )
    pro_plan = plan_get_by_code(code=PlanCode.PRO)
    subscription = subscription_get_for_user(user=user)
    subscription.plan = pro_plan
    subscription.save(update_fields=["plan"])
    return user


@pytest.fixture
def another_user() -> User:
    user = user_create(
        email="sweta@mail.com",
        password="sweta",
    )
    pro_plan = plan_get_by_code(code=PlanCode.PRO)
    subscription = subscription_get_for_user(user=user)
    subscription.plan = pro_plan
    subscription.save(update_fields=["plan"])
    return user


@pytest.fixture
def webhook_endpoint(
    settings,
    user,
) -> WebhookEndpoint:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    return webhook_endpoint_create(
        owner=user,
        name="Test endpoint",
        url="https://example.com/webhooks/choto/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    ).endpoint


@pytest.fixture
def webhook_delivery(
    webhook_endpoint,
) -> WebhookDelivery:
    return WebhookDelivery.objects.create(
        endpoint=webhook_endpoint,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        payload={
            "id": "f84f8dd5-29bb-479c-a979-314871c87949",
            "type": WebhookEventType.SHORT_LINK_CREATED,
            "created_at": "2026-07-29T08:00:00+00:00",
            "data": {
                "short_link_id": "cc8680ce-b3ba-49fb-a982-45687466ca19",
                "short_code": "docs",
                "destination_url": "https://example.com/docs",
            },
        },
    )


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_client(
    api_client: APIClient,
    user: User,
) -> APIClient:
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    return api_client
