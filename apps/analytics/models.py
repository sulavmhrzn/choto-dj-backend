import uuid

from django.db import models


class ClickEvent(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    short_link = models.ForeignKey(
        "links.ShortLink",
        on_delete=models.CASCADE,
        related_name="click_events",
    )
    clicked_at = models.DateTimeField(auto_now_add=True)
    referrer = models.URLField(max_length=2048, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-clicked_at"]
        indexes = [
            models.Index(
                fields=["short_link", "-clicked_at"], name="click_link_time_idx"
            ),
            models.Index(fields=["clicked_at"], name="click_time_idx"),
        ]

    def __str__(self):
        return f"{self.short_link.short_code} at {self.clicked_at}"
