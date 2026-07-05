import asyncio
import time
import uuid

import asyncpg
import requests
from prefect import get_run_logger, task
from prefect.cache_policies import NO_CACHE
from prometheus_client import CollectorRegistry, Histogram, push_to_gateway

from config import Settings


async def _write_test_change(pool: asyncpg.Pool, marker: str) -> None:
    # Clear previous benchmark rows so they don't pile up or get retrieved
    # instead of the new marker.
    await pool.execute("DELETE FROM documents WHERE title = 'freshness-benchmark'")
    await pool.execute(
        "INSERT INTO documents (title, content) VALUES ($1, $2)",
        "freshness-benchmark",
        f"Freshness benchmark canary. The unique canary phrase is {marker}.",
    )


def _poll_until_queryable(settings: Settings, marker: str) -> float | None:
    """Polls the query API (bypassing the answer cache -- see query.py's
    bypass_cache field) until the canary marker shows up in a retrieved
    chunk. Returns elapsed seconds, or None on timeout.

    This is the Section 1 freshness invariant made concrete: "a document
    change in Postgres is queryable in the vector index within X seconds."
    """
    start = time.monotonic()
    deadline = start + settings.freshness_poll_timeout_seconds
    query_text = f"What is the unique canary phrase, {marker}?"

    while time.monotonic() < deadline:
        response = requests.post(
            f"{settings.query_api_url}/query",
            json={"query": query_text, "top_k": 3, "bypass_cache": True, "retrieval_only": True},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if any(marker in r["content"] for r in body["results"]):
            return time.monotonic() - start
        time.sleep(settings.freshness_poll_interval_seconds)

    return None


def _push_latency(settings: Settings, latency_seconds: float) -> None:
    registry = CollectorRegistry()
    histogram = Histogram(
        "freshdex_freshness_latency_seconds",
        "Time from a Postgres change to it being queryable in the vector index (Section 1)",
        registry=registry,
    )
    histogram.observe(latency_seconds)
    push_to_gateway(settings.pushgateway_url, job="freshdex-freshness-benchmark", registry=registry)


@task(cache_policy=NO_CACHE)
async def run_freshness_benchmark(settings: Settings, pool: asyncpg.Pool) -> float | None:
    logger = get_run_logger()
    marker = uuid.uuid4().hex[:12]

    await _write_test_change(pool, marker)
    # _poll_until_queryable is a blocking (requests + sleep) loop -- run it
    # off the event loop so this stays a well-behaved async task.
    latency = await asyncio.to_thread(_poll_until_queryable, settings, marker)

    if latency is None:
        logger.warning("freshness benchmark timed out after %ss", settings.freshness_poll_timeout_seconds)
        return None

    logger.info("freshness benchmark: change queryable after %.2fs", latency)
    _push_latency(settings, latency)
    return latency
