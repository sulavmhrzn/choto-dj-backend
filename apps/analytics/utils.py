from django.http import HttpRequest
from rest_framework.request import Request


def get_client_ip(*, request: HttpRequest | Request) -> str | None:
    forwarded_for: str | None = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")
