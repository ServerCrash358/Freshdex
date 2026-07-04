from prometheus_client import Histogram

# Section 6: "Optionally also instrument the query-api for a live
# (non-synthetic) freshness signal, not just the benchmark job." Observes
# how old (now - indexed_at) each document returned in a live query result
# actually was -- a real-traffic proxy for freshness, distinct from the
# synthetic Prefect benchmark (milestone 8) which measures a single
# controlled write's propagation time.
query_result_age_seconds = Histogram(
    "freshdex_query_result_age_seconds",
    "Age (now - indexed_at) of documents returned in live query results",
)
