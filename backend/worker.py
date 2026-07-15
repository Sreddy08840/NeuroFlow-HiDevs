import asyncio
import uuid
from typing import Any
from arq import create_pool
from arq.connections import RedisSettings
from backend.config import settings
from backend.db.pool import create_db_pool, close_db_pool
from backend.db.migrations import check_and_apply_migrations
from evaluation.judge import EvaluationJudge
import asyncpg


async def process_evaluation_job(ctx: Any, run_id: str) -> None:
    # Fetch query, answer, and chunks from database
    pool = ctx["db_pool"]
    async with pool.acquire() as conn:
        # Get pipeline run details
        run = await conn.fetchrow("""
            SELECT query, generation, retrieved_chunk_ids
            FROM pipeline_runs WHERE id = $1
        """, uuid.UUID(run_id))
        if not run:
            return

        query = run["query"]
        answer = run["generation"]
        retrieved_chunk_ids = run["retrieved_chunk_ids"]

        # Get chunk contents
        chunks = []
        if retrieved_chunk_ids:
            chunk_records = await conn.fetch("""
                SELECT content FROM chunks WHERE id = ANY($1)
                ORDER BY array_position($1::uuid[], id)
            """, retrieved_chunk_ids)
            chunks = [rec["content"] for rec in chunk_records]

    # Run evaluation
    judge = EvaluationJudge(pool)
    await judge.evaluate(uuid.UUID(run_id), query, answer, chunks)


async def startup(ctx: Any) -> None:
    ctx["db_pool"] = await create_db_pool()
    await check_and_apply_migrations()


async def shutdown(ctx: Any) -> None:
    await close_db_pool()


class WorkerSettings:
    functions = [process_evaluation_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 3
    retry_jobs = True
