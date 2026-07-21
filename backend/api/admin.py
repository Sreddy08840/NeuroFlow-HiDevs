import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, Depends

from backend.api.auth import require_scope
from backend.db.pool import get_db_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

# Initialize scheduler
scheduler = AsyncIOScheduler()


async def run_data_retention() -> None:
    """Daily job to clean up old data."""
    logger.info("Running data retention job")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Delete old pipeline runs without evaluations
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        deleted_runs = await conn.fetchval("""
            DELETE FROM pipeline_runs
            WHERE created_at < $1
              AND status = 'complete'
              AND NOT EXISTS (SELECT 1 FROM evaluations WHERE evaluations.run_id = pipeline_runs.id)
            RETURNING COUNT(*)
        """, ninety_days_ago)
        logger.info(f"Deleted {deleted_runs} old pipeline runs")

        # Delete old evaluations
        one_eighty_days_ago = datetime.utcnow() - timedelta(days=180)
        deleted_evals = await conn.fetchval("""
            DELETE FROM evaluations
            WHERE created_at < $1
            RETURNING COUNT(*)
        """, one_eighty_days_ago)
        logger.info(f"Deleted {deleted_evals} old evaluations")

        # Delete chunks from archived documents
        deleted_chunks = await conn.fetchval("""
            DELETE FROM chunks
            WHERE document_id IN (SELECT id FROM documents WHERE status = 'archived')
            RETURNING COUNT(*)
        """)
        logger.info(f"Deleted {deleted_chunks} chunks from archived documents")

    logger.info("Data retention job completed")


@router.on_event("startup")
async def start_scheduler() -> None:
    """Start the scheduled jobs when the app starts."""
    if not scheduler.running:
        scheduler.add_job(run_data_retention, "cron", hour=2, minute=0)  # Run daily at 2 AM UTC
        scheduler.start()
        logger.info("Data retention scheduler started")


@router.on_event("shutdown")
async def stop_scheduler() -> None:
    """Stop the scheduler when the app shuts down."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Data retention scheduler stopped")


@router.post("/retention/run", dependencies=[Depends(require_scope("admin"))])
async def trigger_retention_job():
    """Manually trigger the data retention job."""
    await run_data_retention()
    return {"status": "ok", "message": "Retention job completed"}


@router.post("/circuit-breaker/reset", dependencies=[Depends(require_scope("admin"))])
async def reset_circuit_breaker(provider: str = "openai"):
    """Reset the circuit breaker for a specific provider."""
    from backend.resilience.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(provider)
    await cb.reset()
    return {"status": "ok", "provider": provider, "message": "Circuit breaker reset"}
