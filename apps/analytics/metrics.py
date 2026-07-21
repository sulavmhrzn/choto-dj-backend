from prometheus_client import Counter

click_event_dispatch_total = Counter(
    "choto_click_event_dispatch_total",
    "Total number of click-event task dispatch attempts.",
    labelnames=["outcome"],
)
