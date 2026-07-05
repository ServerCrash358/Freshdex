import asyncio
import logging

import redis.asyncio as redis
from prometheus_client import start_http_server

from .config import Settings
from .consumer import CacheInvalidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    settings = Settings()
    start_http_server(settings.metrics_port)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await CacheInvalidator(settings, redis_client).run()
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
