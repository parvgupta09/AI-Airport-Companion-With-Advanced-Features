import os
import logging
import redis.asyncio as redis
from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", REDIS_URL)

redis_pool = redis.from_url(
    REDIS_URL,
    decode_responses = True,
    max_connections = 20
)

async def get_redis() -> redis.Redis:
    return redis_pool