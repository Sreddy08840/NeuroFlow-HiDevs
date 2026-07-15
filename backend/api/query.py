import asyncio
import json
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pipelines.generation import Generator


router = APIRouter(prefix="/query", tags=["query"])


# In-memory store for active streams (for demonstration; in production, use Redis)
active_streams: Dict[str, asyncio.Queue] = {}


class QueryRequest(BaseModel):
    query: str = Field(..., description="User's question")
    pipeline_id: uuid.UUID = Field(..., description="Pipeline ID to use")
    stream: bool = Field(default=False, description="Whether to stream the response")


class QueryResponse(BaseModel):
    run_id: str
    response: str
    citations: list


@router.post("")
async def create_query(request: QueryRequest, background_tasks: BackgroundTasks):
    if request.stream:
        # For streaming, create queue first
        queue = asyncio.Queue()
        real_run_id = None

        # Start generation in background
        async def run_generation():
            generator = Generator()
            try:
                async for event in generator.generate_stream(
                    request.query, request.pipeline_id
                ):
                    await queue.put(event)
            finally:
                await queue.put(None)  # Signal end
                if real_run_id and real_run_id in active_streams:
                    del active_streams[real_run_id]

        background_tasks.add_task(run_generation)

        # Wait for run_id event
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=10.0)
                if event is None:
                    raise HTTPException(status_code=500, detail="Generation failed to start")
                await queue.put(event)  # Put back so it's sent to client
                if event["type"] == "run_id":
                    real_run_id = event["run_id"]
                    active_streams[real_run_id] = queue
                    return {"run_id": real_run_id}
        except asyncio.TimeoutError:
            raise HTTPException(status_code=500, detail="Failed to get run ID")

    else:
        # Non-streaming: generate and return full response
        generator = Generator()
        result = await generator.generate(request.query, request.pipeline_id)
        return QueryResponse(
            run_id=result.run_id,
            response=result.full_response,
            citations=[
                {
                    "source": c.reference,
                    "chunk_id": c.chunk_id,
                    "document": c.document_name,
                    "page": c.page_number,
                    "invalid_citation": c.invalid_citation
                }
                for c in result.citations
            ]
        )


async def event_generator(run_id: str):
    if run_id not in active_streams:
        yield ServerSentEvent(data=json.dumps({"type": "error", "message": "Run not found"}))
        return

    queue = active_streams[run_id]
    last_event_time = asyncio.get_event_loop().time()

    while True:
        try:
            # Wait for event with timeout to send keepalives
            event = await asyncio.wait_for(queue.get(), timeout=15.0)
            if event is None:
                break
            yield ServerSentEvent(data=json.dumps(event))
            last_event_time = asyncio.get_event_loop().time()
        except asyncio.TimeoutError:
            # Send keepalive
            current_time = asyncio.get_event_loop().time()
            if current_time - last_event_time >= 15:
                yield ServerSentEvent(data=json.dumps({"type": "keepalive"}))
                last_event_time = current_time


@router.get("/{run_id}/stream")
async def stream_query(run_id: str):
    return EventSourceResponse(event_generator(run_id))
