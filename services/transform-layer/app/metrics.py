from prometheus_client import Counter

# Section 6: checksum miss-rate, resolved to live in the transform layer
# (the location the doc left open, per the resolution in milestone 3).
checksums_matched_total = Counter(
    "freshdex_checksums_matched_total",
    "Checksum comparisons that matched an already-indexed doc (no re-embed needed)",
)
checksums_mismatched_total = Counter(
    "freshdex_checksums_mismatched_total",
    "Checksum comparisons that mismatched (enqueued for re-embed)",
)
