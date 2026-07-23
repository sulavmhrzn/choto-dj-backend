from dataclasses import dataclass

from apps.accounts.models import APIKey


@dataclass(frozen=True)
class CreatedAPIKey:
    api_key: APIKey
    secret: str
