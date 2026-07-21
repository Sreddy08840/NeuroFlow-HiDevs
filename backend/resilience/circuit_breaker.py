import time

import redis.asyncio as redis

from backend.config import settings
from backend.monitoring.metrics import active_circuit_breakers_open, circuit_breaker_trips


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        redis_client: redis.Redis | None = None
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.redis_client = redis_client or redis.from_url(settings.redis_url)
        
        # Redis keys
        self.state_key = f"circuit:{name}:state"
        self.failure_count_key = f"circuit:{name}:failure_count"
        self.opened_at_key = f"circuit:{name}:opened_at"
        self.half_open_calls_key = f"circuit:{name}:half_open_calls"
    
    async def _get_state(self) -> str:
        state = await self.redis_client.get(self.state_key)
        if not state:
            return "closed"
        state = state.decode("utf-8")
        
        if state == "open":
            opened_at = float(await self.redis_client.get(self.opened_at_key) or 0)
            if time.time() - opened_at >= self.recovery_timeout:
                # Transition to half-open
                await self.redis_client.set(self.state_key, "half-open")
                await self.redis_client.set(self.half_open_calls_key, 0)
                return "half-open"
        
        return state
    
    async def _increment_failure(self) -> None:
        count = await self.redis_client.incr(self.failure_count_key)
        if count >= self.failure_threshold:
            # Check if circuit was closed before (to avoid duplicate tripping)
            old_state = await self._get_state()
            if old_state in ("closed", "half-open"):
                circuit_breaker_trips.labels(provider=self.name).inc()
                # Update active circuit breakers gauge
                await self._update_active_circuit_breakers_gauge()
            await self.redis_client.set(self.state_key, "open")
            await self.redis_client.set(self.opened_at_key, time.time())
    
    async def _update_active_circuit_breakers_gauge(self) -> None:
        # Count number of open circuit breakers
        open_count = 0
        for provider in ["openai", "anthropic"]:
            cb = CircuitBreaker(provider, redis_client=self.redis_client)
            state = await cb._get_state()
            if state == "open":
                open_count += 1
        active_circuit_breakers_open.set(open_count)
    
    async def _reset_failure(self) -> None:
        await self.redis_client.set(self.failure_count_key, 0)
        await self.redis_client.set(self.state_key, "closed")
        await self._update_active_circuit_breakers_gauge()
    
    async def __aenter__(self):
        state = await self._get_state()
        
        if state == "open":
            raise CircuitOpenError(f"Circuit breaker '{self.name}' is open")
        
        if state == "half-open":
            count = await self.redis_client.incr(self.half_open_calls_key)
            if count > self.half_open_max_calls:
                raise CircuitOpenError(f"Circuit breaker '{self.name}' is half-open and max calls exceeded")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success
            await self._reset_failure()
        else:
            # Failure
            await self._increment_failure()
            # If in half-open and failed, open circuit again
            if await self._get_state() == "half-open":
                await self.redis_client.set(self.state_key, "open")
                await self.redis_client.set(self.opened_at_key, time.time())
    
    async def get_status(self) -> dict:
        state = await self._get_state()
        failure_count = int(await self.redis_client.get(self.failure_count_key) or 0)
        opened_at = await self.redis_client.get(self.opened_at_key)
        return {
            "state": state,
            "failure_count": failure_count,
            "opened_at": opened_at.decode("utf-8") if opened_at else None
        }
