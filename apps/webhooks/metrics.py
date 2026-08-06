from prometheus_client import Counter

webhook_delivery_attempts_total = Counter(
    "choto_webhook_delivery_attempts_total", "Total webhook delivery attempts."
)

webhook_delivery_outcomes_total = Counter(
    "choto_webhook_delivery_outcomes_total",
    "Webhook delivery outcomes.",
    labelnames=["outcomes"],
)

webhook_delivery_retries_total = Counter(
    "choto_webhook_delivery_retries_total", "Total webhook delivery retries scheduled"
)
