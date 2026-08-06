from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.webhooks.constants import (
    WEBHOOK_MAX_DELIVERY_ATTEMPTS,
    WEBHOOK_RESPONSE_BODY_MAX_LENGTH,
)
from apps.webhooks.encryption import decrypt_webhook_secret
from apps.webhooks.models import (
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEventType,
)
from apps.webhooks.services import (
    webhook_deliveries_create_for_event,
    webhook_deliveries_dispatch,
    webhook_delivery_send,
    webhook_delivery_should_retry,
    webhook_endpoint_create,
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


@pytest.mark.django_db
def test_webhook_deliveries_create_for_event_creates_delivery_per_endpoint(
    settings, user
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    first_endpoint = webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/analytics/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    ).endpoint
    second_endpoint = webhook_endpoint_create(
        owner=user,
        name="CRM",
        url="https://example.com/crm/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    ).endpoint

    webhook_endpoint_create(
        owner=user,
        name="Clicks only",
        url="https://example.com/clicks/",
        events=[WebhookEventType.SHORT_LINK_CLICKED],
    )

    created_at = timezone.make_aware(
        datetime(
            year=2026,
            month=7,
            day=28,
            hour=12,
        )
    )

    deliveries = webhook_deliveries_create_for_event(
        owner=user,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        data={"short_code": "docs"},
        created_at=created_at,
    )

    assert len(deliveries) == 2
    assert WebhookDelivery.objects.count() == 2
    assert {delivery.endpoint.id for delivery in deliveries} == {
        first_endpoint.id,
        second_endpoint.id,
    }


@pytest.mark.django_db
def test_webhook_deliveries_share_event_id_and_payload(
    settings,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    for index in range(2):
        webhook_endpoint_create(
            owner=user,
            name=f"Endpoint {index}",
            url=f"https://example.com/{index}/",
            events=[
                WebhookEventType.SHORT_LINK_CREATED,
            ],
        )

    deliveries = webhook_deliveries_create_for_event(
        owner=user,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        data={
            "short_code": "docs",
        },
    )

    assert len(deliveries) == 2
    assert deliveries[0].event_id == deliveries[1].event_id
    assert deliveries[0].payload == deliveries[1].payload

    assert deliveries[0].payload["id"] == str(deliveries[0].event_id)


@pytest.mark.django_db
def test_webhook_deliveries_start_pending(
    settings,
    user,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    deliveries = webhook_deliveries_create_for_event(
        owner=user,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        data={
            "short_code": "docs",
        },
    )

    delivery = deliveries[0]

    assert delivery.status == WebhookDeliveryStatus.PENDING
    assert delivery.attempt_count == 0
    assert delivery.response_status is None
    assert delivery.delivered_at is None


@pytest.mark.django_db
def test_webhook_deliveries_create_for_event_returns_empty_list(
    user,
) -> None:
    deliveries = webhook_deliveries_create_for_event(
        owner=user,
        event_type=WebhookEventType.SHORT_LINK_CREATED,
        data={
            "short_code": "docs",
        },
    )

    assert deliveries == []
    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_webhook_deliveries_dispatch_enqueues_after_commit(
    django_capture_on_commit_callbacks,
    monkeypatch,
    webhook_delivery,
) -> None:
    dispatched_ids: list[str] = []

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_delivery_send_task.delay",
        lambda *, delivery_id: dispatched_ids.append(delivery_id),
    )

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        webhook_deliveries_dispatch(
            deliveries=[
                webhook_delivery,
            ]
        )

        assert dispatched_ids == []

    assert len(callbacks) == 1

    callbacks[0]()

    assert dispatched_ids == [str(webhook_delivery.id)]


@pytest.mark.django_db
def test_webhook_deliveries_dispatch_does_nothing_when_empty(
    django_capture_on_commit_callbacks,
) -> None:
    with django_capture_on_commit_callbacks(
        execute=False,
    ) as callbacks:
        webhook_deliveries_dispatch(
            deliveries=[],
        )

    assert callbacks == []


@pytest.mark.django_db
def test_webhook_delivery_send_marks_delivery_succeeded(monkeypatch, webhook_delivery):
    captured_request: dict[str, object] = {}

    def mock_post(
        url: str, *, content: str, headers: dict[str, str], timeout: int
    ) -> httpx.Response:
        captured_request.update(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "timeout": timeout,
            }
        )

        return httpx.Response(status_code=200, text="received")

    monkeypatch.setattr("apps.webhooks.services.httpx.post", mock_post)

    result = webhook_delivery_send(delivery_id=webhook_delivery.id)

    assert result is not None

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.SUCCEEDED
    assert webhook_delivery.attempt_count == 1
    assert webhook_delivery.response_status == 200
    assert webhook_delivery.response_body == "received"
    assert webhook_delivery.error_message == ""
    assert webhook_delivery.delivered_at is not None
    assert webhook_delivery.next_attempt_at is None

    assert captured_request["url"] == webhook_delivery.endpoint.url
    assert captured_request["content"]
    assert captured_request["headers"]["Content-Type"] == "application/json"
    assert captured_request["headers"]["Choto-Signature"].startswith("v1=")


@pytest.mark.django_db
def test_webhook_delivery_send_marks_non_2xx_response_failed(
    monkeypatch, webhook_delivery
):
    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        lambda *args, **kwargs: httpx.Response(
            status_code=500, text="Internal server error"
        ),
    )

    result = webhook_delivery_send(delivery_id=webhook_delivery.id)

    assert result is not None

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.FAILED
    assert webhook_delivery.attempt_count == 1
    assert webhook_delivery.response_status == 500
    assert webhook_delivery.response_body == "Internal server error"
    assert webhook_delivery.error_message == ""
    assert webhook_delivery.delivered_at is None


@pytest.mark.django_db
def test_webhook_delivery_send_records_network_failure(monkeypatch, webhook_delivery):
    def raise_timeout(*args, **kwargs):
        raise httpx.ConnectTimeout("Connection timed out.")

    monkeypatch.setattr("apps.webhooks.services.httpx.post", raise_timeout)

    result = webhook_delivery_send(delivery_id=webhook_delivery.id)

    assert result is not None

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.FAILED
    assert webhook_delivery.attempt_count == 1
    assert webhook_delivery.response_status is None
    assert webhook_delivery.response_status is None
    assert webhook_delivery.response_body == ""
    assert "Connection timed out." in webhook_delivery.error_message
    assert webhook_delivery.delivered_at is None


@pytest.mark.django_db
def test_webhook_delivery_send_does_not_call_inactive_endpoint(
    monkeypatch, webhook_delivery
):
    webhook_delivery.endpoint.is_active = False
    webhook_delivery.endpoint.save(update_fields=["is_active"])

    def unexpected_post(*args, **kwargs):
        raise AssertionError("Inactive endpoint must not receive an HTTP request.")

    monkeypatch.setattr("apps.webhooks.services.httpx.post", unexpected_post)
    result = webhook_delivery_send(
        delivery_id=webhook_delivery.id,
    )

    assert result is not None

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.FAILED
    assert webhook_delivery.attempt_count == 0
    assert webhook_delivery.error_message == "Webhook endpoint is inactive."
    assert webhook_delivery.next_attempt_at is None


@pytest.mark.django_db
def test_webhook_delivery_send_truncates_response_body(
    monkeypatch,
    webhook_delivery,
) -> None:
    response_body = "x" * (WEBHOOK_RESPONSE_BODY_MAX_LENGTH + 500)

    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        lambda *args, **kwargs: httpx.Response(
            status_code=400,
            text=response_body,
        ),
    )

    webhook_delivery_send(
        delivery_id=webhook_delivery.id,
    )

    webhook_delivery.refresh_from_db()

    assert len(webhook_delivery.response_body) == (WEBHOOK_RESPONSE_BODY_MAX_LENGTH)
    assert (
        webhook_delivery.response_body
        == (response_body[:WEBHOOK_RESPONSE_BODY_MAX_LENGTH])
    )


@pytest.mark.django_db
def test_webhook_delivery_send_does_not_resend_succeeded_delivery(
    monkeypatch,
    webhook_delivery,
) -> None:
    webhook_delivery.status = WebhookDeliveryStatus.SUCCEEDED
    webhook_delivery.attempt_count = 1
    webhook_delivery.response_status = 200
    webhook_delivery.save(
        update_fields=[
            "status",
            "attempt_count",
            "response_status",
        ]
    )

    def unexpected_post(*args, **kwargs) -> None:
        raise AssertionError("Succeeded delivery must not be sent again.")

    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        unexpected_post,
    )

    result = webhook_delivery_send(
        delivery_id=webhook_delivery.id,
    )

    assert result is not None

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.SUCCEEDED
    assert webhook_delivery.attempt_count == 1


@pytest.mark.django_db
def test_webhook_delivery_send_returns_none_for_missing_delivery():
    result = webhook_delivery_send(
        delivery_id=uuid4(),
    )

    assert result is None


@pytest.mark.django_db
def test_webhook_delivery_send_attempts_failed_delivery_again(
    monkeypatch,
    webhook_delivery,
) -> None:
    webhook_delivery.status = WebhookDeliveryStatus.FAILED
    webhook_delivery.attempt_count = 1
    webhook_delivery.error_message = "Previous failure"
    webhook_delivery.save(
        update_fields=[
            "status",
            "attempt_count",
            "error_message",
        ]
    )

    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        lambda *args, **kwargs: httpx.Response(
            status_code=200,
            text="received",
        ),
    )

    webhook_delivery_send(
        delivery_id=webhook_delivery.id,
    )

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.SUCCEEDED
    assert webhook_delivery.attempt_count == 2
    assert webhook_delivery.error_message == ""
    assert webhook_delivery.response_status == 200


def test_webhook_delivery_should_retry_network_failure():
    should_retry = webhook_delivery_should_retry(response_status=None, attempt_count=1)
    assert should_retry is True


def test_webhook_delivery_should_retry_request_timeout():
    should_retry = webhook_delivery_should_retry(response_status=408, attempt_count=1)
    assert should_retry is True


def test_webhook_delivery_should_retry_rate_limit() -> None:
    should_retry = webhook_delivery_should_retry(
        response_status=429,
        attempt_count=1,
    )

    assert should_retry is True


@pytest.mark.parametrize(
    "response_status",
    [
        500,
        502,
        503,
        504,
        599,
    ],
)
def test_webhook_delivery_should_retry_server_errors(
    response_status: int,
):
    should_retry = webhook_delivery_should_retry(
        response_status=response_status,
        attempt_count=1,
    )

    assert should_retry is True


@pytest.mark.parametrize(
    "response_status",
    [
        200,
        201,
        204,
    ],
)
def test_webhook_delivery_should_not_retry_successful_responses(
    response_status: int,
):
    should_retry = webhook_delivery_should_retry(
        response_status=response_status,
        attempt_count=1,
    )

    assert should_retry is False


@pytest.mark.parametrize(
    "response_status",
    [
        None,
        408,
        429,
        500,
    ],
)
def test_webhook_delivery_should_not_retry_after_maximum_attempts(
    response_status: int | None,
) -> None:
    should_retry = webhook_delivery_should_retry(
        response_status=response_status,
        attempt_count=WEBHOOK_MAX_DELIVERY_ATTEMPTS,
    )

    assert should_retry is False


def test_webhook_delivery_should_retry_before_maximum_attempts():
    should_retry = webhook_delivery_should_retry(
        response_status=500,
        attempt_count=WEBHOOK_MAX_DELIVERY_ATTEMPTS - 1,
    )

    assert should_retry is True


@pytest.mark.django_db
def test_webhook_delivery_send_schedules_retry_for_server_error(
    monkeypatch, webhook_delivery
):
    before_send = timezone.now()

    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        lambda *args, **kwargs: httpx.Response(status_code=500, text="Server error"),
    )

    webhook_delivery_send(delivery_id=webhook_delivery.id)

    after_send = timezone.now()
    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.FAILED
    assert webhook_delivery.attempt_count == 1
    assert webhook_delivery.next_attempt_at is not None

    assert (
        before_send + timedelta(seconds=60)
        <= webhook_delivery.next_attempt_at
        <= after_send + timedelta(seconds=60)
    )


@pytest.mark.django_db
def test_webhook_delivery_send_schedules_retry_for_network_failure(
    monkeypatch, webhook_delivery
):
    def raise_timeout(*args, **kwargs):
        raise httpx.ConnectTimeout("Timed out.")

    monkeypatch.setattr("apps.webhooks.services.httpx.post", raise_timeout)

    webhook_delivery_send(delivery_id=webhook_delivery.id)

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.next_attempt_at is not None


@pytest.mark.django_db
def test_webhook_delivery_send_does_not_schedule_retry_for_client_error(
    monkeypatch, webhook_delivery
):
    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        lambda *args, **kwargs: httpx.Response(status_code=400, text="Bad request"),
    )

    webhook_delivery_send(delivery_id=webhook_delivery.id)

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.status == WebhookDeliveryStatus.FAILED
    assert webhook_delivery.next_attempt_at is None


@pytest.mark.django_db
def test_webhook_delivery_send_stops_retrying_after_maximum_attempts(
    monkeypatch,
    webhook_delivery,
):
    webhook_delivery.attempt_count = WEBHOOK_MAX_DELIVERY_ATTEMPTS - 1
    webhook_delivery.save(
        update_fields=[
            "attempt_count",
        ]
    )

    monkeypatch.setattr(
        "apps.webhooks.services.httpx.post",
        lambda *args, **kwargs: httpx.Response(
            status_code=500,
            text="Server error",
        ),
    )

    webhook_delivery_send(
        delivery_id=webhook_delivery.id,
    )

    webhook_delivery.refresh_from_db()

    assert webhook_delivery.attempt_count == WEBHOOK_MAX_DELIVERY_ATTEMPTS
    assert webhook_delivery.next_attempt_at is None
