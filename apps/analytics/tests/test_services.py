import pytest
from cryptography.fernet import Fernet

from apps.accounts.models import User
from apps.analytics.models import ClickEvent
from apps.analytics.services import click_event_create
from apps.links.models import ShortLink
from apps.links.services import short_link_create
from apps.webhooks.models import WebhookDelivery, WebhookEventType
from apps.webhooks.services import webhook_endpoint_create


@pytest.fixture
def user() -> User:
    return User.objects.create_user(email="sulav@mail.com", password="sulavmhrzn")


@pytest.fixture
def short_link(user) -> ShortLink:
    return short_link_create(
        owner=user,
        destination_url="https://example.com/first",
        short_code="portfolio",
    )


@pytest.mark.django_db
def test_click_event_create_dispatches_webhook_after_commit(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Clicks",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    )

    with django_capture_on_commit_callbacks(
        execute=False,
    ) as callbacks:
        click_event = click_event_create(
            short_link=short_link,
            referrer="https://google.com/",
            user_agent="pytest",
            ip_address="127.0.0.1",
        )

        assert ClickEvent.objects.filter(
            id=click_event.id,
        ).exists()

        assert WebhookDelivery.objects.count() == 0

    for callback in callbacks:
        callback()

    assert WebhookDelivery.objects.count() == 1


@pytest.mark.django_db
def test_short_link_clicked_webhook_contains_click_data(
    settings,
    user,
    short_link,
    django_capture_on_commit_callbacks,
    monkeypatch,
) -> None:
    settings.WEBHOOK_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")

    webhook_endpoint_create(
        owner=user,
        name="Clicks",
        url="https://example.com/webhooks/",
        events=[
            WebhookEventType.SHORT_LINK_CLICKED,
        ],
    )

    monkeypatch.setattr(
        "apps.webhooks.tasks.webhook_delivery_send_task.delay",
        lambda **kwargs: None,
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        click_event = click_event_create(
            short_link=short_link,
            referrer="https://google.com/",
            user_agent="pytest-agent",
            ip_address="127.0.0.1",
        )

    delivery = WebhookDelivery.objects.get()

    assert delivery.event_type == WebhookEventType.SHORT_LINK_CLICKED

    assert delivery.payload["data"] == {
        "click_event_id": str(click_event.id),
        "short_link_id": str(short_link.id),
        "short_code": short_link.short_code,
        "clicked_at": click_event.clicked_at.isoformat(),
        "referrer": "https://google.com/",
        "user_agent": "pytest-agent",
    }

    assert "ip_address" not in delivery.payload["data"]


@pytest.mark.django_db
def test_click_event_create_does_not_create_delivery_without_subscriber(
    short_link,
    django_capture_on_commit_callbacks,
) -> None:
    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        click_event_create(
            short_link=short_link,
            referrer="",
            user_agent="pytest",
            ip_address=None,
        )

    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_webhook_failure_does_not_remove_click_event(
    short_link, django_capture_on_commit_callbacks, monkeypatch
):
    def raise_webhook_failure():
        raise RuntimeError("Webhook failure.")

    monkeypatch.setattr(
        "apps.webhooks.services.webhook_event_dispatch",
        raise_webhook_failure,
    )

    with django_capture_on_commit_callbacks(execute=True):
        click_event = click_event_create(
            short_link=short_link,
            referrer="",
            user_agent="pytest",
            ip_address=None,
        )

    assert ClickEvent.objects.filter(id=click_event.id).exists()
