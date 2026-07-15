import asyncpg
import redis.asyncio as redis
from typing import Tuple
from db.pool import get_db_pool
from config import settings


async def check_postgres() -> bool:
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        return True
    except Exception:
        return False


async def check_mlflow() -> bool:
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.search_experiments(max_results=1)
        return True
    except Exception:
        return False


async def get_health_checks() -> Tuple[bool, bool, bool]:
    postgres_ok = await check_postgres()
    redis_ok = await check_redis()
    mlflow_ok = await check_mlflow()
    return postgres_ok, redis_ok, mlflow_ok
