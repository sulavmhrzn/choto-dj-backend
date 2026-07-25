import uuid

from django.conf import settings
from django.db import models

from apps.links.models import ShortLink


class IdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    key = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROCESSING
    )
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_data = models.JSONField(null=True, blank=True)
    short_link = models.ForeignKey(
        ShortLink,
        on_delete=models.SET_NULL,
        related_name="idempotency_records",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "key"], name="unique_idempotency_key_per_owner"
            )
        ]
        indexes = [models.Index(fields=["expires_at"], name="idempotency_expiry_idx")]

    def __str__(self) -> str:
        return f"{self.owner.id}:{self.key}"
