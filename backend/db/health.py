import asyncio

import redis.asyncio as redis
from config import settings
from db.pool import get_db_pool


async def check_postgres() -> dict:
    try:
        start = asyncio.get_event_loop().time()
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception:
        return {"status": "critical", "latency_ms": None}


async def check_redis() -> dict:
    try:
        start = asyncio.get_event_loop().time()
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception:
        return {"status": "critical", "latency_ms": None}


async def check_mlflow() -> dict:
    try:
        start = asyncio.get_event_loop().time()
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.search_experiments(max_results=1)
        latency = int((asyncio.get_event_loop().time() - start) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception:
        return {"status": "degraded", "latency_ms": None}


async def get_health_checks() -> tuple[dict, dict, dict]:
    postgres = await check_postgres()
    redis = await check_redis()
    mlflow = await check_mlflow()
    return postgres, redis, mlflow
