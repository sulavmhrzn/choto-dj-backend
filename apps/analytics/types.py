from datetime import datetime
from typing import TypedDict


class ClickEventSummary(TypedDict):
    total_clicks: int
    clicks_since: int
    unique_visitors: int
    first_clicked_at: datetime | None
    last_clicked_at: datetime | None
