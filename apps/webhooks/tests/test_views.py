import pytest
from cryptography.fernet import Fernet
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.services import api_key_create
from apps.webhooks.encryption import decrypt_webhook_secret
from apps.webhooks.models import WebhookEndpoint, WebhookEventType
from apps.webhooks.services import webhook_endpoint_create, webhook_endpoint_update


@pytest.fixture
def user() -> User:
    return User.objects.create_user(
        email="sulav@mail.com",
        password="sulavmhrzn",
    )


@pytest.fixture
def another_user() -> User:
    return User.objects.create_user(
        email="sweta@mail.com",
        password="sweta",
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


@pytest.mark.django_db
def test_webhook_endpoint_create_returns_secret_once(
    settings, authenticated_client, user
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    response = authenticated_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "Production analytics",
            "url": "https://example.com/webhooks/choto/",
            "events": [
                WebhookEventType.SHORT_LINK_CREATED,
                WebhookEventType.SHORT_LINK_CLICKED,
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert response.data["name"] == "Production analytics"
    assert response.data["url"] == "https://example.com/webhooks/choto/"
    assert response.data["events"] == [
        WebhookEventType.SHORT_LINK_CREATED,
        WebhookEventType.SHORT_LINK_CLICKED,
    ]
    assert response.data["is_active"] is True
    assert response.data["secret"].startswith("whsec_")

    endpoint = WebhookEndpoint.objects.get(id=response.data["id"])

    assert endpoint.owner == user
    assert endpoint.encrypted_secret != response.data["secret"]

    assert (
        decrypt_webhook_secret(encrypted_secret=endpoint.encrypted_secret)
        == response.data["secret"]
    )


@pytest.mark.django_db
def test_webhook_endpoint_create_does_not_expose_encrypted_secret(
    settings,
    authenticated_client,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    response = authenticated_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "CRM",
            "url": "https://example.com/webhooks/",
            "events": [
                WebhookEventType.SHORT_LINK_CREATED,
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert "secret" in response.data
    assert "encrypted_secret" not in response.data
    assert "owner" not in response.data


@pytest.mark.django_db
def test_webhook_endpoint_create_rejects_duplicate_events(
    settings,
    authenticated_client,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    response = authenticated_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "Analytics",
            "url": "https://example.com/webhooks/",
            "events": [
                WebhookEventType.SHORT_LINK_CLICKED,
                WebhookEventType.SHORT_LINK_CLICKED,
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WebhookEndpoint.objects.count() == 0


@pytest.mark.django_db
def test_webhook_endpoint_create_rejects_unknown_event(
    settings,
    authenticated_client,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    response = authenticated_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "Analytics",
            "url": "https://example.com/webhooks/",
            "events": [
                "short_link.unknown",
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WebhookEndpoint.objects.count() == 0


@pytest.mark.django_db
def test_webhook_endpoint_create_rejects_empty_events(
    settings,
    authenticated_client,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    response = authenticated_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "Analytics",
            "url": "https://example.com/webhooks/",
            "events": [],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert WebhookEndpoint.objects.count() == 0


@pytest.mark.django_db
def test_webhook_endpoint_create_requires_authentication(
    settings,
    api_client,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    response = api_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "Analytics",
            "url": "https://example.com/webhooks/",
            "events": [
                WebhookEventType.SHORT_LINK_CREATED,
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert WebhookEndpoint.objects.count() == 0


@pytest.mark.django_db
def test_api_key_cannot_create_webhook_endpoint(
    settings,
    api_client,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created_api_key = api_key_create(
        owner=user,
        name="Automation",
    )

    response = api_client.post(
        reverse("webhooks:endpoint-list-create"),
        data={
            "name": "Analytics",
            "url": "https://example.com/webhooks/",
            "events": [
                WebhookEventType.SHORT_LINK_CREATED,
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"Api-Key {created_api_key.secret}",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert WebhookEndpoint.objects.count() == 0


@pytest.mark.django_db
def test_webhook_endpoint_list_returns_only_users_endpoints(
    settings,
    authenticated_client,
    user,
    another_user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Production",
        url="https://example.com/production/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )
    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/analytics/",
        events=[
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    )
    webhook_endpoint_create(
        owner=another_user,
        name="Other user",
        url="https://example.com/other/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    response = authenticated_client.get(
        reverse("webhooks:endpoint-list-create"),
    )

    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 2
    assert {item["name"] for item in response.data} == {
        "Production",
        "Analytics",
    }


@pytest.mark.django_db
def test_webhook_endpoint_list_does_not_expose_secrets(
    settings,
    authenticated_client,
    user: User,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Production",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    response = authenticated_client.get(
        reverse("webhooks:endpoint-list-create"),
    )

    assert response.status_code == status.HTTP_200_OK

    endpoint_data = response.data[0]

    assert "secret" not in endpoint_data
    assert "encrypted_secret" not in endpoint_data
    assert "owner" not in endpoint_data


@pytest.mark.django_db
def test_webhook_endpoint_list_returns_empty_list(
    authenticated_client,
) -> None:
    response = authenticated_client.get(
        reverse("webhooks:endpoint-list-create"),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.django_db
def test_webhook_endpoint_list_requires_authentication(
    api_client,
) -> None:
    response = api_client.get(
        reverse("webhooks:endpoint-list-create"),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_webhook_endpoint_update_changes_provided_fields(
    settings,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Old name",
        url="https://example.com/old/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    original_encrypted_secret = created.endpoint.encrypted_secret

    updated_endpoint = webhook_endpoint_update(
        endpoint=created.endpoint,
        name="New name",
        url="https://example.com/new/",
        events=[
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
        is_active=False,
    )

    updated_endpoint.refresh_from_db()

    assert updated_endpoint.name == "New name"
    assert updated_endpoint.url == "https://example.com/new/"
    assert updated_endpoint.events == [
        WebhookEventType.SHORT_LINK_CLICKED,
    ]
    assert updated_endpoint.is_active is False

    assert updated_endpoint.encrypted_secret == original_encrypted_secret


@pytest.mark.django_db
def test_webhook_endpoint_update_returns_endpoint_when_nothing_changes(
    settings,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    original_updated_at = created.endpoint.updated_at

    updated_endpoint = webhook_endpoint_update(
        endpoint=created.endpoint,
    )

    updated_endpoint.refresh_from_db()

    assert updated_endpoint.updated_at == original_updated_at


@pytest.mark.django_db
def test_webhook_endpoint_detail_returns_owned_endpoint(
    settings,
    authenticated_client,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    response = authenticated_client.get(
        reverse(
            "webhooks:endpoint-detail",
            kwargs={
                "endpoint_id": created.endpoint.id,
            },
        )
    )

    assert response.status_code == status.HTTP_200_OK

    assert response.data["id"] == str(created.endpoint.id)
    assert response.data["name"] == "Analytics"
    assert "secret" not in response.data
    assert "encrypted_secret" not in response.data


@pytest.mark.django_db
def test_webhook_endpoint_detail_returns_not_found_for_other_users_endpoint(
    settings,
    authenticated_client,
    another_user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=another_user,
        name="Other user",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    response = authenticated_client.get(
        reverse(
            "webhooks:endpoint-detail",
            kwargs={
                "endpoint_id": created.endpoint.id,
            },
        )
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_webhook_endpoint_update_updates_owned_endpoint(
    settings,
    authenticated_client,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Old name",
        url="https://example.com/old/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    original_encrypted_secret = created.endpoint.encrypted_secret

    response = authenticated_client.patch(
        reverse(
            "webhooks:endpoint-detail",
            kwargs={
                "endpoint_id": created.endpoint.id,
            },
        ),
        data={
            "name": "New name",
            "events": [
                WebhookEventType.SHORT_LINK_CLICKED,
            ],
            "is_active": False,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    assert response.data["name"] == "New name"
    assert response.data["events"] == [
        WebhookEventType.SHORT_LINK_CLICKED,
    ]
    assert response.data["is_active"] is False
    assert "secret" not in response.data

    created.endpoint.refresh_from_db()

    assert created.endpoint.encrypted_secret == original_encrypted_secret


@pytest.mark.django_db
def test_webhook_endpoint_update_rejects_duplicate_events(
    settings,
    authenticated_client,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    created = webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    response = authenticated_client.patch(
        reverse(
            "webhooks:endpoint-detail",
            kwargs={
                "endpoint_id": created.endpoint.id,
            },
        ),
        data={
            "events": [
                WebhookEventType.SHORT_LINK_CLICKED,
                WebhookEventType.SHORT_LINK_CLICKED,
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
