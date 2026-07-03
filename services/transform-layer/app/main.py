import asyncio
import logging

from .checksum_store import ChecksumStore
from .config import Settings
from .consumer import TransformLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    settings = Settings()
    checksum_store = ChecksumStore(settings.postgres_dsn)
    await checksum_store.connect()
    try:
        await TransformLayer(settings, checksum_store).run()
    finally:
        await checksum_store.close()


if __name__ == "__main__":
    asyncio.run(main())
