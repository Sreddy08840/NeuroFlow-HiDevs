import asyncio
from typing import Optional, Any
import redis.asyncio as redis
from backend.config import settings


class TimeoutError(Exception):
    pass


class TimeoutManager:
    timeouts = {
        "embedding": 10,
        "chat_completion": 60,
        "reranking": 15,
        "evaluation": 120,
        "file_extraction": 30,
        "url_fetch": 15
    }
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.from_url(settings.redis_url)
    
    async def execute_with_timeout(
        self, task_type: str, coro: Any
    ):
        timeout = self.timeouts.get(task_type, 30)
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            # Increment timeout counter in Redis
            await self.redis_client.incr(f"timeouts:{task_type}")
            raise TimeoutError(f"{task_type} timed out after {timeout} seconds")
