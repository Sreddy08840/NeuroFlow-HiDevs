from typing import Optional
import redis.asyncio as redis
from backend.config import settings


class BackpressureManager:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.from_url(settings.redis_url)
        self.queue_key = "queue:ingest"
        self.high_threshold = 50
        self.full_threshold = 100
    
    async def get_queue_depth(self) -> int:
        return await self.redis_client.llen(self.queue_key)
    
    async def check_backpressure(self) -> tuple[str, dict]:
        """Check ingestion queue backpressure and return status and response data."""
        queue_depth = await self.get_queue_depth()
        estimated_wait = queue_depth * 2  # Rough estimate, 2s per item
        
        if queue_depth >= self.full_threshold:
            return "unavailable", {
                "error": "ingestion_queue_full",
                "queue_depth": queue_depth,
                "retry_after": 30
            }
        elif queue_depth >= self.high_threshold:
            return "warning", {
                "warning": "high_queue_depth",
                "queue_depth": queue_depth,
                "estimated_wait_minutes": round(estimated_wait / 60, 1)
            }
        else:
            return "ok", {}
