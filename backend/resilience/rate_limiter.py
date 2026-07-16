import asyncio
import time
from typing import Optional
import redis.asyncio as redis
from backend.config import settings


class RateLimiter:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.from_url(settings.redis_url)
        
        # Provider rate limits: tokens per bucket, tokens per second replenishment
        self.provider_configs = {
            "openai": {"max_tokens": 3000, "replenish_rate": 50}
        }
    
    async def _check_token_bucket(
        self, key: str, max_tokens: int, replenish_rate: float, consume: int = 1
    ) -> tuple[bool, Optional[float]]:
        """Check token bucket and consume tokens if available. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        
        # Get current state (tokens, last_update)
        data = await self.redis_client.get(key)
        if data is None:
            tokens = max_tokens
            last_update = now
        else:
            tokens, last_update = map(float, data.decode("utf-8").split(","))
        
        # Replenish tokens since last update
        elapsed = now - last_update
        tokens += elapsed * replenish_rate
        tokens = min(tokens, max_tokens)
        last_update = now
        
        # Check if we have enough tokens
        if tokens >= consume:
            tokens -= consume
            await self.redis_client.setex(
                key,
                int(max_tokens / replenish_rate) + 60,  # Expire after enough time to fully replenish
                f"{tokens},{last_update}"
            )
            return True, None
        else:
            # Not enough tokens, calculate wait time
            needed = consume - tokens
            wait = needed / replenish_rate
            return False, wait
    
    async def check_provider_rate_limit(self, provider: str) -> tuple[bool, Optional[float]]:
        """Check provider-level rate limit."""
        config = self.provider_configs.get(provider, {"max_tokens": 1000, "replenish_rate": 16.67})
        key = f"rpb:{provider}:tokens"
        return await self._check_token_bucket(key, config["max_tokens"], config["replenish_rate"])
    
    async def check_pipeline_rate_limit(
        self, pipeline_id: str, rate_limit_rpm: int = 60
    ) -> tuple[bool, Optional[float]]:
        """Check per-pipeline rate limit (requests per minute)."""
        max_tokens = rate_limit_rpm
        replenish_rate = rate_limit_rpm / 60.0
        key = f"rpb:pipeline:{pipeline_id}:tokens"
        return await self._check_token_bucket(key, max_tokens, replenish_rate)
    
    async def check_endpoint_rate_limit(
        self, endpoint: str, ip: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, Optional[float]]:
        """Check endpoint-level rate limit using sliding window counter."""
        now = time.time()
        window_start = now - window_seconds
        
        key = f"endpoint:{endpoint}:{ip}"
        
        # Add current request timestamp
        await self.redis_client.zadd(key, {str(now): now})
        
        # Remove old entries
        await self.redis_client.zremrangebyscore(key, 0, window_start)
        
        # Count requests in current window
        count = await self.redis_client.zcard(key)
        
        # Set expiration
        await self.redis_client.expire(key, window_seconds + 60)
        
        if count <= max_requests:
            return True, None
        else:
            # Get the oldest request in current window
            oldest = (await self.redis_client.zrange(key, 0, 0, withscores=True))[0][1]
            retry_after = window_seconds - (now - oldest)
            return False, max(retry_after, 1)
