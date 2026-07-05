import asyncio
import logging

import asyncpg
from prefect import flow

logger = logging.getLogger("freshdex-eval")

from config import Settings
from freshness_benchmark import run_freshness_benchmark
from ragas_eval import run_ragas_eval

logging.basicConfig(level=logging.INFO)


@flow(name="freshdex-eval")
async def freshdex_eval_flow() -> None:
    settings = Settings()
    pool = await asyncpg.create_pool(settings.postgres_dsn, min_size=1, max_size=3)
    try:
        # Two independent measurements per Section 4: freshness benchmark
        # (produces the P95 freshness number for Section 6) and RAGAS eval
        # (faithfulness/answer-relevancy against the golden set). Run
        # sequentially, not concurrently -- both hit the same query API and
        # embedding worker, and the freshness benchmark's timing shouldn't
        # be skewed by RAGAS eval load running at the same time.
        await run_freshness_benchmark(settings, pool)
        await run_ragas_eval(settings, pool)
    finally:
        await pool.close()


async def _run_forever() -> None:
    settings = Settings()
    # flow.serve(interval=...) needs a real Prefect server to persist the
    # schedule against ("Cannot schedule flows on an ephemeral server") --
    # standing one up is unnecessary infra for a local demo. A plain loop
    # gets the same outcome (a scheduled recurring flow run) while still
    # going through @flow/@task for Prefect's logging/retries.
    while True:
        try:
            await freshdex_eval_flow()
        except Exception:
            # A failed run (e.g. a transient Gemini 503) shouldn't crash the
            # container -- restart:unless-stopped would just retry
            # immediately with no backoff, which is exactly what turns a
            # transient upstream error into a rate-limit-exhausting crash
            # loop. Log it and wait for the next scheduled interval instead.
            logger.exception("eval flow run failed, will retry next interval")
        await asyncio.sleep(settings.schedule_interval_seconds)


if __name__ == "__main__":
    asyncio.run(_run_forever())
