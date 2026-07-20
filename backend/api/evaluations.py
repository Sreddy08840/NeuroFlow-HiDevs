from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
import asyncio
import json
from typing import AsyncGenerator
from backend.db.pool import get_db_pool

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

# In-memory channel for SSE (in production, use Redis Pub/Sub)
evaluation_channel = asyncio.Queue()

@router.get(
    "",
    tags=["Evaluations"],
    summary="List evaluations",
    description="Get a paginated list of all evaluation results, most recent first"
)
async def list_evaluations(
    limit: int = Field(50, ge=1, le=100, description="Number of evaluations to return per page"),
    offset: int = Field(0, ge=0, description="Number of evaluations to skip")
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                e.id as evaluation_id,
                e.run_id,
                e.faithfulness,
                e.answer_relevance,
                e.context_precision,
                e.context_recall,
                e.overall_score,
                e.user_rating,
                e.created_at,
                pr.query
            FROM evaluations e
            JOIN pipeline_runs pr ON e.run_id = pr.id
            ORDER BY e.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return [dict(row) for row in rows]

@router.get(
    "/stream",
    tags=["Evaluations"],
    summary="Stream new evaluations",
    description="Server-Sent Events (SSE) endpoint to receive new evaluation results as they are created"
)
async def stream_evaluations(request: Request) -> EventSourceResponse:
    async def event_generator() -> AsyncGenerator[ServerSentEvent, None]:
        while True:
            if await request.is_disconnected():
                break
            
            # Check for new evaluations
            try:
                # Wait for a new evaluation (with timeout to check for disconnection)
                evaluation = await asyncio.wait_for(evaluation_channel.get(), timeout=1.0)
                yield ServerSentEvent(data=json.dumps(evaluation))
            except TimeoutError:
                continue
    
    return EventSourceResponse(event_generator())

# Helper function to send new evaluation to SSE stream
async def broadcast_evaluation(evaluation: dict):
    await evaluation_channel.put(evaluation)
