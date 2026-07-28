import pytest
from cryptography.fernet import Fernet

from apps.accounts.models import User
from apps.webhooks.encryption import decrypt_webhook_secret
from apps.webhooks.models import WebhookEndpoint, WebhookEventType
from apps.webhooks.services import webhook_endpoint_create


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@mail.com",
        password="sulavmhrzn",
    )


@pytest.mark.django_db
def test_webhook_endpoint_create_encrypts_secret(settings, user):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Production analytics",
        url="https://example.com/webhooks/choto/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    )

    endpoint = created.endpoint

    assert endpoint.owner == user
    assert endpoint.name == "Production analytics"
    assert endpoint.is_active is True
    assert created.secret.startswith("whsec_")

    assert endpoint.encrypted_secret != created.secret

    decrypted_secret = decrypt_webhook_secret(
        encrypted_secret=endpoint.encrypted_secret
    )
    assert decrypted_secret == created.secret


@pytest.mark.django_db
def test_webhook_endpoint_create_creates_endpoint(
    settings,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="CRM",
        url="https://example.com/choto/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    assert WebhookEndpoint.objects.count() == 1
    assert WebhookEndpoint.objects.get() == created.endpoint
