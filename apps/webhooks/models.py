import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class WebhookEventType(models.TextChoices):
    SHORT_LINK_CREATED = ("short_link.created", "Short link created")
    SHORT_LINK_UPDATED = ("short_link.updated", "Short link updated")
    SHORT_LINK_DELETED = ("short_link.deleted", "Short link deleted")
    SHORT_LINK_CLICKED = ("short_link.clicked", "Short link clicked")


class WebhookDeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class WebhookEndpoint(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
    )

    name = models.CharField(max_length=100)
    url = models.URLField(max_length=500)
    events = ArrayField(
        base_field=models.CharField(
            max_length=50,
            choices=WebhookEventType.choices,
        ),
        default=list,
    )
    encrypted_secret = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"


class WebhookDelivery(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    event_type = models.CharField(
        max_length=50,
        choices=WebhookEventType.choices,
        db_index=True,
    )
    payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=WebhookDeliveryStatus.choices,
        default=WebhookDeliveryStatus.PENDING,
        db_index=True,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    next_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "next_attempt_at",
                ],
                name="webhook_retry_lookup_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_type} -> {self.endpoint.name}"
