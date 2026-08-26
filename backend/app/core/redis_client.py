import os
import logging
import redis.asyncio as redis
from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)

redis_pool = redis.from_url(
    REDIS_URL,
    decode_responses = True,
    max_connections = 20,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    health_check_interval=30
)

async def get_redis() -> redis.Redis:
    return redis_pool