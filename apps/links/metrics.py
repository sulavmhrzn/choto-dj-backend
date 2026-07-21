from prometheus_client import Counter

short_links_created_total = Counter(
    "choto_short_links_created_total",
    "Total number of short links created.",
)

short_link_redirects_total = Counter(
    "choto_short_link_redirects_total",
    "Total number of short-link redirect attempts.",
    labelnames=["outcome"],
)
