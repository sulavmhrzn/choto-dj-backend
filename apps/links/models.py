import uuid

from django.conf import settings
from django.db import models


class ShortLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="short_links"
    )
    short_code = models.CharField(max_length=32, unique=True)
    destination_url = models.URLField(max_length=2048)
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["owner", "-created_at"], name="link_owner_created_idx"
            ),
            models.Index(
                fields=["owner", "is_active"],
                name="link_owner_active_idx",
            ),
        ]

    def __str__(self):
        return self.short_code
