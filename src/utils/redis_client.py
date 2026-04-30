import redis
from src.utils.config import config
from src.utils.logger import logger

_redis_client = None


def get_redis_client() -> redis.Redis:
    """Get Redis client singleton with connection pooling"""
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                config.REDIS_URL,
                decode_responses=True,
                socket_timeout=30,
                socket_connect_timeout=5
            )
            # Test connection
            _redis_client.ping()
            logger.info(f"Redis connected to {config.REDIS_URL}")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {str(e)}")
            raise

    return _redis_client
