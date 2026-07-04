import asyncio
import logging

from prometheus_client import start_http_server

from .checksum_store import ChecksumStore
from .config import Settings
from .consumer import TransformLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    settings = Settings()
    # start_http_server runs its own thread, non-blocking for the asyncio
    # event loop -- Prometheus scrapes this directly (Section 6).
    start_http_server(settings.metrics_port)
    checksum_store = ChecksumStore(settings.postgres_dsn)
    await checksum_store.connect()
    try:
        await TransformLayer(settings, checksum_store).run()
    finally:
        await checksum_store.close()


if __name__ == "__main__":
    asyncio.run(main())
