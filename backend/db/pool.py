
import asyncpg
from config import settings

_pool: asyncpg.Pool | None = None


async def create_db_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url)


async def get_db_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
