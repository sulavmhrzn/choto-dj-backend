from prometheus_client import Counter

short_links_created_total = Counter(
    "choto_short_links_created_total",
    "Total number of short links created.",
)
