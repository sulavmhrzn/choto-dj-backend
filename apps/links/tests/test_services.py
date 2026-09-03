from datetime import timedelta
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.billing.exceptions import PlanLimitExceededError
from apps.billing.selectors import subscription_get_for_user
from apps.links import services
from apps.links.models import ShortLink
from apps.links.services import (
    short_link_create,
    short_link_deactivate_expired,
    short_link_delete,
    short_link_update,
)
from apps.webhooks.models import WebhookDelivery, WebhookEventType
from apps.webhooks.services import webhook_endpoint_create


@pytest.mark.django_db
def test_short_link_create_rejects_duplicate_custom_alias(user):
    short_link_create(
        owner=user,
        destination_url="https://example.com/first",
        short_code="portfolio",
    )

    with pytest.raises(
        ValueError,
        match="This custom alias is already in use.",
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com/second",
            short_code="portfolio",
        )


@pytest.mark.django_db
def test_short_link_create_runs_side_effects_after_commit(
    user, monkeypatch, django_capture_on_commit_callbacks
):
    cache_delete_mock = Mock()
    metric_increment_mock = Mock()

    monkeypatch.setattr(services, "short_link_redirect_cache_delete", cache_delete_mock)
    monkeypatch.setattr(
        services.short_links_created_total, "inc", metric_increment_mock
    )

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        link = short_link_create(
            owner=user,
            destination_url="https://example.com",
            title="Example",
        )

        cache_delete_mock.assert_not_called()
        metric_increment_mock.assert_not_called()

    assert len(callbacks) == 1
    callbacks[0]()

    cache_delete_mock.assert_called_once_with(short_code=link.short_code)
    metric_increment_mock.assert_called_once_with()


@pytest.mark.django_db
def test_short_link_deactivate_expired_deactivates_only_expired_active_links(
    user, monkeypatch, django_capture_on_commit_callbacks
):
    now = timezone.now()

    expired_link = ShortLink.objects.create(
        owner=user,
        short_code="expired-link",
        destination_url="https://example.com/expired",
        is_active=True,
        expires_at=now - timedelta(minutes=1),
    )

    future_link = ShortLink.objects.create(
        owner=user,
        short_code="future-link",
        destination_url="https://example.com/future",
        is_active=True,
        expires_at=now + timedelta(days=3),
    )

    inactive_expired_link = ShortLink.objects.create(
        owner=user,
        short_code="inactive-expired",
        destination_url="https://example.com/inactive",
        is_active=False,
        expires_at=now - timedelta(days=3),
    )

    non_expiring_link = ShortLink.objects.create(
        owner=user,
        short_code="never-expires",
        destination_url="https://example.com/permanent",
        is_active=True,
        expires_at=None,
    )

    cache_delete_mock = Mock()

    monkeypatch.setattr(services, "short_link_redirect_cache_delete", cache_delete_mock)

    with django_capture_on_commit_callbacks(execute=True):
        updated_count = short_link_deactivate_expired()

    assert updated_count == 1

    expired_link.refresh_from_db()
    future_link.refresh_from_db()
    inactive_expired_link.refresh_from_db()
    non_expiring_link.refresh_from_db()

    assert expired_link.is_active is False
    assert future_link.is_active is True
    assert inactive_expired_link.is_active is False
    assert non_expiring_link.is_active is True

    cache_delete_mock.assert_called_once_with(short_code=expired_link.short_code)


@pytest.mark.django_db
def test_short_link_deactivate_expired_returns_zero_when_none_exist(
    user,
    monkeypatch,
):
    ShortLink.objects.create(
        owner=user,
        short_code="future-link",
        destination_url="https://example.com",
        is_active=True,
        expires_at=timezone.now() + timedelta(days=1),
    )

    cache_delete_mock = Mock()

    monkeypatch.setattr(
        services,
        "short_link_redirect_cache_delete",
        cache_delete_mock,
    )

    updated_count = short_link_deactivate_expired()

    assert updated_count == 0
    cache_delete_mock.assert_not_called()


@pytest.mark.django_db
def test_short_link_create_dispatches_webhook_after_commit(
    settings, user, django_capture_on_commit_callbacks
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")
    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    )

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        short_link = short_link_create(
            owner=user,
            destination_url="https://example.com/docs",
            title="Documentation",
        )

        assert ShortLink.objects.filter(id=short_link.id).exists()

        assert WebhookDelivery.objects.count() == 0

    assert len(callbacks) == 1

    callbacks[0]()

    assert WebhookDelivery.objects.count() == 1


@pytest.mark.django_db
def test_short_link_created_webhook_contains_expected_payload(
    settings, user, django_capture_on_commit_callbacks, monkeypatch
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    )

    dispatched_delivery_ids: list[str] = []

    monkeypatch.setattr(
        "apps.webhooks.tasks.webhook_delivery_send_task.delay",
        lambda *, delivery_id: dispatched_delivery_ids.append(delivery_id),
    )

    with django_capture_on_commit_callbacks(execute=True):
        short_link = short_link_create(
            owner=user,
            destination_url="https://example.com/docs",
            title="Documentation",
        )

    delivery = WebhookDelivery.objects.get()

    assert delivery.event_type == WebhookEventType.SHORT_LINK_CREATED
    assert delivery.payload["type"] == WebhookEventType.SHORT_LINK_CREATED
    assert delivery.payload["data"] == {
        "short_link_id": str(short_link.id),
        "short_code": short_link.short_code,
        "destination_url": short_link.destination_url,
        "title": short_link.title,
        "is_active": short_link.is_active,
        "expires_at": None,
        "created_at": short_link.created_at.isoformat(),
    }

    assert dispatched_delivery_ids == [str(delivery.id)]


@pytest.mark.django_db
def test_short_link_create_does_not_dispatch_to_unsubscribed_endpoint(
    settings,
    user,
    django_capture_on_commit_callbacks,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Clicks only",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com",
        )

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_create_does_not_dispatch_to_inactive_endpoint(
    settings,
    user,
    django_capture_on_commit_callbacks,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    endpoint = webhook_endpoint_create(
        owner=user,
        name="Disabled",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    ).endpoint

    endpoint.is_active = False
    endpoint.save(
        update_fields=[
            "is_active",
        ]
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com",
        )

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_created_webhook_uses_same_event_id_for_all_endpoints(
    settings,
    user,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    for index in range(2):
        webhook_endpoint_create(
            owner=user,
            name=f"Endpoint {index}",
            url=f"https://example.com/webhooks/{index}/",
            events=[
                WebhookEventType.SHORT_LINK_CREATED,
            ],
        )

    monkeypatch.setattr(
        "apps.webhooks.tasks.webhook_delivery_send_task.delay",
        lambda **kwargs: None,
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com",
        )

    deliveries = list(WebhookDelivery.objects.order_by("created_at"))

    assert len(deliveries) == 2
    assert deliveries[0].event_id == deliveries[1].event_id
    assert deliveries[0].payload == deliveries[1].payload


@pytest.mark.django_db
def test_webhook_dispatch_failure_does_not_remove_created_short_link(
    user,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    def failing_webhook_event_dispatch(**kwargs) -> None:
        raise RuntimeError("Webhook failure.")

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_event_dispatch",
        failing_webhook_event_dispatch,
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link = short_link_create(
            owner=user,
            destination_url="https://example.com",
        )

    assert ShortLink.objects.filter(
        id=short_link.id,
    ).exists()


@pytest.mark.django_db
def test_short_link_update_dispatches_webhook_after_commit(
    settings, user, short_link, django_capture_on_commit_callbacks
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Updates",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_UPDATED],
    )
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        updated_link = short_link_update(link=short_link, title="Updated title")

        assert updated_link.title == "Updated title"
        assert WebhookDelivery.objects.count() == 0

    callbacks[0]()

    assert WebhookDelivery.objects.count() == 1


@pytest.mark.django_db
def test_short_link_updated_webhook_contains_changed_fields(
    settings, user, short_link, django_capture_on_commit_callbacks, monkeypatch
):
    settings.WBEHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Updates",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_UPDATED],
    )

    with django_capture_on_commit_callbacks(execute=True):
        updated_link = short_link_update(
            link=short_link,
            title="New title",
            destination_url="https://example.com/new/",
        )

    delivery = WebhookDelivery.objects.get()

    assert delivery.event_type == WebhookEventType.SHORT_LINK_UPDATED
    assert delivery.payload["type"] == WebhookEventType.SHORT_LINK_UPDATED
    assert delivery.payload["data"] == {
        "short_link_id": str(updated_link.id),
        "short_code": updated_link.short_code,
        "destination_url": updated_link.destination_url,
        "title": updated_link.title,
        "is_active": updated_link.is_active,
        "expires_at": (
            updated_link.expires_at.isoformat()
            if updated_link.expires_at is not None
            else None
        ),
        "updated_at": updated_link.updated_at.isoformat(),
        "changed_fields": [
            "destination_url",
            "title",
            "updated_at",
        ],
    }


@pytest.mark.django_db
def test_short_link_update_does_not_dispatch_when_nothing_changes(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Updates",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_UPDATED,
        ],
    )

    original_updated_at = short_link.updated_at

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        updated_link = short_link_update(
            link=short_link,
            title=short_link.title,
            destination_url=short_link.destination_url,
        )

    updated_link.refresh_from_db()

    assert updated_link.updated_at == original_updated_at
    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_update_does_not_dispatch_to_unsubscribed_endpoint(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Created events only",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CREATED,
        ],
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link_update(
            link=short_link,
            title="Updated title",
        )

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_update_does_not_dispatch_to_inactive_endpoint(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    endpoint = webhook_endpoint_create(
        owner=user,
        name="Disabled updates",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_UPDATED,
        ],
    ).endpoint

    endpoint.is_active = False
    endpoint.save(
        update_fields=[
            "is_active",
        ]
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link_update(
            link=short_link,
            title="Updated title",
        )

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_webhook_dispatch_failure_does_not_undo_short_link_update(
    user,
    short_link,
    django_capture_on_commit_callbacks,
    monkeypatch,
) -> None:
    def failing_webhook_event_dispatch(**kwargs) -> None:
        raise RuntimeError("Webhook dispatch failed.")

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_event_dispatch",
        failing_webhook_event_dispatch,
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        updated_link = short_link_update(
            link=short_link,
            title="Updated title",
        )

    updated_link.refresh_from_db()

    assert updated_link.title == "Updated title"


@pytest.mark.django_db
def test_short_link_updated_webhook_uses_same_event_id_for_all_endpoints(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
    monkeypatch,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    for index in range(2):
        webhook_endpoint_create(
            owner=user,
            name=f"Update endpoint {index}",
            url=f"https://example.com/webhooks/{index}/",
            events=[
                WebhookEventType.SHORT_LINK_UPDATED,
            ],
        )

    monkeypatch.setattr(
        "apps.webhooks.tasks.webhook_delivery_send_task.delay",
        lambda **kwargs: None,
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        short_link_update(
            link=short_link,
            title="Updated title",
        )

    deliveries = list(WebhookDelivery.objects.order_by("created_at"))

    assert len(deliveries) == 2
    assert deliveries[0].event_id == deliveries[1].event_id
    assert deliveries[0].payload == deliveries[1].payload


@pytest.mark.django_db
def test_short_link_delete_dispatches_webhook_after_commit(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")
    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_DELETED],
    )
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        short_link_delete(link=short_link)

        assert ShortLink.objects.count() == 0
        assert short_link.id is None
        assert WebhookDelivery.objects.count() == 0

    callbacks[0]()

    assert WebhookDelivery.objects.count() == 1


@pytest.mark.django_db
def test_short_link_delete_does_not_dispatch_to_unsubscribed_endpoints(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_CREATED],
    )

    with django_capture_on_commit_callbacks(execute=True):
        short_link_delete(link=short_link)

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_delete_does_not_dispatch_to_inactive_endpoint(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    endpoint = webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_DELETED],
    ).endpoint
    endpoint.is_active = False
    endpoint.save(update_fields=["is_active"])

    with django_capture_on_commit_callbacks(execute=True):
        short_link_delete(link=short_link)

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_deleted_webhook_contains_deleted_link_data(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Analytics",
        url="https://example.com/webhooks/",
        events=[WebhookEventType.SHORT_LINK_DELETED],
    )

    short_link_id = short_link.id
    short_code = short_link.short_code
    destination_url = short_link.destination_url
    title = short_link.title
    is_active = short_link.is_active
    expires_at = short_link.expires_at
    created_at = short_link.created_at

    with django_capture_on_commit_callbacks(execute=True):
        short_link_delete(link=short_link)

    delivery = WebhookDelivery.objects.get()

    assert delivery.event_type == WebhookEventType.SHORT_LINK_DELETED
    assert delivery.payload["type"] == WebhookEventType.SHORT_LINK_DELETED
    assert delivery.payload["data"] == {
        "short_link_id": str(short_link_id),
        "short_code": short_code,
        "destination_url": destination_url,
        "title": title,
        "is_active": is_active,
        "expires_at": (expires_at.isoformat() if expires_at is not None else None),
        "created_at": created_at.isoformat(),
    }


@pytest.mark.django_db
def test_webhook_dispatch_failure_does_not_undo_short_link_delete(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    def failing_webhook_event_dispatch():
        raise RuntimeError("Webhook event dispatch failed")

    monkeypatch.setattr(
        "apps.links.services.webhook_event_dispatch", failing_webhook_event_dispatch
    )

    with django_capture_on_commit_callbacks(execute=True):
        short_link_delete(link=short_link)

    assert short_link.id is None
    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_short_link_create_fails_when_plan_limit_reached(user, short_link):
    subscription = subscription_get_for_user(user=user)
    subscription.plan.short_link_limit = 1
    subscription.plan.save(update_fields=["short_link_limit"])

    with pytest.raises(
        PlanLimitExceededError, match="Short link limit reached for current plan."
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com",
            title="Limit reached",
        )


@pytest.mark.django_db
def test_short_link_create_succeeds_below_plan_limit(
    user,
):
    subscription = user.subscription

    subscription.plan.short_link_limit = 1
    subscription.plan.save(
        update_fields=["short_link_limit"],
    )

    link = short_link_create(
        owner=user,
        destination_url="https://example.com",
        title="Limit reached",
    )

    assert link.owner == user
