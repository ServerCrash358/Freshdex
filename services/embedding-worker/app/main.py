import asyncio
import logging

from .config import Settings
from .consumer import RequestConsumer
from .db import create_pool
from .embedder import build_embedder
from .tombstone_consumer import TombstoneConsumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    settings = Settings()
    pool = await create_pool(settings.postgres_dsn)
    embedder = build_embedder(settings.embedder_backend, settings.embedder_model)

    requests = RequestConsumer(settings, pool, embedder)
    tombstones = TombstoneConsumer(settings, pool)

    # Two independent consumer loops, running concurrently -- separate
    # topics, separate consumer groups, separate failure domains.
    await asyncio.gather(requests.run(), tombstones.run())


if __name__ == "__main__":
    asyncio.run(main())
