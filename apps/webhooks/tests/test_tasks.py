from uuid import uuid4

import pytest

from apps.webhooks.models import WebhookDeliveryStatus
from apps.webhooks.tasks import webhook_delivery_send_task


@pytest.mark.django_db
def test_webhook_delivery_send_task_calls_service(monkeypatch, webhook_delivery):
    received_delivery_ids = []

    def mock_webhook_delivery_send(*, delivery_id):
        received_delivery_ids.append(delivery_id)
        return webhook_delivery

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_delivery_send", mock_webhook_delivery_send
    )

    result = webhook_delivery_send_task(delivery_id=str(webhook_delivery.id))

    assert result is None
    assert received_delivery_ids == [webhook_delivery.id]


@pytest.mark.django_db
def test_webhook_delivery_send_task_handles_missing_delivery(monkeypatch):
    monkeypatch.setattr(
        "apps.webhooks.services.webhook_delivery_send", lambda *, delivery_id: None
    )

    result = webhook_delivery_send_task(delivery_id=str(uuid4()))

    assert result is None


@pytest.mark.django_db
def test_webhook_delivery_send_task_handles_successful_delivery(
    monkeypatch, webhook_delivery
):
    webhook_delivery.status = WebhookDeliveryStatus.SUCCEEDED
    webhook_delivery.attempt_count = 1
    webhook_delivery.response_status = 200

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_delivery_send",
        lambda *, delivery_id: webhook_delivery,
    )

    result = webhook_delivery_send_task(delivery_id=str(webhook_delivery.id))

    assert result is None


@pytest.mark.django_db
def test_webhook_delivery_send_task_handles_failed_delivery(
    monkeypatch,
    webhook_delivery,
):
    webhook_delivery.status = WebhookDeliveryStatus.FAILED
    webhook_delivery.attempt_count = 1
    webhook_delivery.response_status = 500

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_delivery_send",
        lambda *, delivery_id: webhook_delivery,
    )

    result = webhook_delivery_send_task(
        delivery_id=str(webhook_delivery.id),
    )

    assert result is None


@pytest.mark.django_db
def test_webhook_delivery_send_task_rejects_invalid_delivery_id():
    with pytest.raises(ValueError):
        webhook_delivery_send_task(
            delivery_id="not-a-uuid",
        )
