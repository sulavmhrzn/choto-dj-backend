from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class WebhookSecretDecryptionError(Exception):
    """Raised when a stored webhook secret cannot be decrypted."""


def _get_fernet() -> Fernet:
    encryption_key = settings.WEBHOOK_ENCRYPTION_KEY

    if not encryption_key:
        raise ImproperlyConfigured("WEBHOOK_ENCRYPTION_KEY must be configured.")

    try:
        return Fernet(encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("WEBHOOK_ENCRYPTION_KEY is invalid.") from exc


def encrypt_webhook_secret(*, secret: str) -> str:
    encrypted_secret = _get_fernet().encrypt(secret.encode("utf-8"))
    return encrypted_secret.decode("utf-8")


def decrypt_webhook_secret(*, encrypted_secret: str) -> str:
    try:
        decrypted_secret = _get_fernet().decrypt(encrypted_secret.encode("utf-8"))
    except InvalidToken as exc:
        raise WebhookSecretDecryptionError(
            "Webhook secret could not be decrypted."
        ) from exc

    return decrypted_secret.decode("utf-8")
