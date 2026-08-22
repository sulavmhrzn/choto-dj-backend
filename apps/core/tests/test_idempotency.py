from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.core.idempotency import build_idempotency_request_hash
from apps.core.models import IdempotencyRecord
from apps.core.services import (
    IDEMPOTENCY_RECORD_TTL,
    idempotency_record_claim,
    idempotency_record_complete,
    idempotency_record_delete_expired,
)
from apps.links.services import short_link_create


def test_idempotency_request_hash_is_independent_of_field_order() -> None:
    first_hash = build_idempotency_request_hash(
        data={
            "destination_url": "https://example.com",
            "title": "Example",
        }
    )
    second_hash = build_idempotency_request_hash(
        data={
            "title": "Example",
            "destination_url": "https://example.com",
        }
    )

    assert first_hash == second_hash


def test_idempotency_request_hash_changes_when_data_changes() -> None:
    first_hash = build_idempotency_request_hash(
        data={
            "destination_url": "https://example.com/one",
        },
    )

    second_hash = build_idempotency_request_hash(
        data={
            "destination_url": "https://example.com/two",
        },
    )

    assert first_hash != second_hash


def test_idempotency_request_hash_supports_datetime_values() -> None:
    expires_at = timezone.make_aware(
        datetime(
            year=2026,
            month=7,
            day=30,
            hour=12,
        )
    )

    request_hash = build_idempotency_request_hash(
        data={
            "destination_url": "https://example.com",
            "expires_at": expires_at,
        },
    )

    assert len(request_hash) == 64


def test_idempotency_request_hash_is_stable_for_same_datetime() -> None:
    expires_at = timezone.make_aware(
        datetime(
            year=2026,
            month=7,
            day=30,
            hour=12,
        )
    )

    first_hash = build_idempotency_request_hash(
        data={
            "expires_at": expires_at,
        },
    )

    second_hash = build_idempotency_request_hash(
        data={
            "expires_at": expires_at,
        },
    )

    assert first_hash == second_hash


def test_idempotency_request_hash_supports_empty_data() -> None:
    first_hash = build_idempotency_request_hash(
        data={},
    )

    second_hash = build_idempotency_request_hash(
        data={},
    )

    assert first_hash == second_hash
    assert len(first_hash) == 64


@pytest.mark.django_db
def test_idempotency_record_claim_creates_new_record(user) -> None:
    before_claim = timezone.now()

    claim = idempotency_record_claim(
        owner=user, key="request-123", request_hash="a" * 64
    )

    after_claim = timezone.now()

    assert claim.created is True
    assert claim.record.owner == user
    assert claim.record.key == "request-123"
    assert claim.record.request_hash == "a" * 64
    assert claim.record.status == IdempotencyRecord.Status.PROCESSING

    assert (
        before_claim + IDEMPOTENCY_RECORD_TTL
        <= claim.record.expires_at
        <= after_claim + IDEMPOTENCY_RECORD_TTL
    )


@pytest.mark.django_db
def test_idempotency_record_claim_returns_existing_record(
    user,
) -> None:
    existing_record = IdempotencyRecord.objects.create(
        owner=user,
        key="request-123",
        request_hash="a" * 64,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    claim = idempotency_record_claim(
        owner=user,
        key="request-123",
        request_hash="a" * 64,
    )

    assert claim.created is False
    assert claim.record == existing_record
    assert IdempotencyRecord.objects.count() == 1


@pytest.mark.django_db
def test_idempotency_record_claim_returns_existing_record_for_different_hash(
    user,
) -> None:
    existing_record = IdempotencyRecord.objects.create(
        owner=user,
        key="request-123",
        request_hash="a" * 64,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    claim = idempotency_record_claim(
        owner=user,
        key="request-123",
        request_hash="b" * 64,
    )

    assert claim.created is False
    assert claim.record == existing_record
    assert claim.record.request_hash == "a" * 64


@pytest.mark.django_db
def test_idempotency_record_claim_replaces_expired_record(
    user,
) -> None:
    expired_record = IdempotencyRecord.objects.create(
        owner=user,
        key="request-123",
        request_hash="old-hash",
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    claim = idempotency_record_claim(
        owner=user,
        key="request-123",
        request_hash="new-hash",
    )

    assert claim.created is True
    assert claim.record.id != expired_record.id
    assert claim.record.request_hash == "new-hash"

    assert not IdempotencyRecord.objects.filter(
        id=expired_record.id,
    ).exists()

    assert IdempotencyRecord.objects.count() == 1


@pytest.mark.django_db
def test_idempotency_record_claim_scopes_key_to_owner(
    user,
    another_user,
) -> None:

    first_claim = idempotency_record_claim(
        owner=user,
        key="shared-key",
        request_hash="a" * 64,
    )

    second_claim = idempotency_record_claim(
        owner=another_user,
        key="shared-key",
        request_hash="b" * 64,
    )

    assert first_claim.created is True
    assert second_claim.created is True
    assert first_claim.record.id != second_claim.record.id
    assert IdempotencyRecord.objects.count() == 2


@pytest.mark.django_db
def test_idempotency_record_complete_stores_response(
    user,
    short_link,
) -> None:

    record = IdempotencyRecord.objects.create(
        owner=user,
        key="request-123",
        request_hash="a" * 64,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    response_data = {
        "id": str(short_link.id),
        "short_code": short_link.short_code,
    }

    completed_record = idempotency_record_complete(
        record=record,
        response_status=status.HTTP_201_CREATED,
        response_data=response_data,
        short_link=short_link,
    )

    record.refresh_from_db()

    assert completed_record == record
    assert record.status == IdempotencyRecord.Status.COMPLETED
    assert record.response_status == status.HTTP_201_CREATED
    assert record.response_data == response_data
    assert record.short_link == short_link


@pytest.mark.django_db
def test_idempotency_record_complete_does_not_overwrite_completed_record(
    user,
    short_link,
    another_user,
) -> None:
    original_link = short_link
    other_link = short_link_create(
        title="Example", destination_url="https://example.com", owner=another_user
    )

    record = IdempotencyRecord.objects.create(
        owner=user,
        key="request-123",
        request_hash="a" * 64,
        status=IdempotencyRecord.Status.COMPLETED,
        response_status=status.HTTP_201_CREATED,
        response_data={
            "id": str(original_link.id),
        },
        short_link=original_link,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    idempotency_record_complete(
        record=record,
        response_status=status.HTTP_200_OK,
        response_data={
            "id": str(other_link.id),
        },
        short_link=other_link,
    )

    record.refresh_from_db()

    assert record.response_status == status.HTTP_201_CREATED
    assert record.response_data == {
        "id": str(original_link.id),
    }
    assert record.short_link == original_link


@pytest.mark.django_db
def test_idempotency_record_delete_expired_deletes_expired_records(
    user,
) -> None:
    expired_record = IdempotencyRecord.objects.create(
        owner=user,
        key="expired-key",
        request_hash="a" * 64,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    deleted_count = idempotency_record_delete_expired()

    assert deleted_count == 1
    assert not IdempotencyRecord.objects.filter(
        id=expired_record.id,
    ).exists()


@pytest.mark.django_db
def test_idempotency_record_delete_expired_preserves_active_records(
    user,
) -> None:
    active_record = IdempotencyRecord.objects.create(
        owner=user,
        key="active-key",
        request_hash="a" * 64,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    deleted_count = idempotency_record_delete_expired()

    assert deleted_count == 0
    assert IdempotencyRecord.objects.filter(
        id=active_record.id,
    ).exists()
