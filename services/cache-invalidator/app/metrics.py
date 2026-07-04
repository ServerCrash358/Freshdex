from prometheus_client import Counter

# Section 6: "Cache invalidation correctness", labeled by trigger: CDC-event
# vs tombstone -- reflects the Section 3.3 decision (CDC-triggered
# invalidation, not embedding.completed-triggered).
cache_keys_invalidated_total = Counter(
    "freshdex_cache_keys_invalidated_total",
    "Cache keys invalidated",
    ["trigger"],
)
