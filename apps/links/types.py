from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RedirectableShortLink:
    id: UUID
    destination_url: str
    expires_at: datetime | None
