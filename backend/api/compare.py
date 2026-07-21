import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipelines.generation import Generator

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class CompareRequest(BaseModel):
    query: str
    pipeline_a_id: str
    pipeline_b_id: str


@dataclass
class PipelineResult:
    run_id: str
    generation: str
    retrieval_latency_ms: int
    total_latency_ms: int
    chunks_used: int
    eval_score: float | None


async def run_pipeline(
    generator: Generator,
    query: str,
    pipeline_id: uuid.UUID
) -> PipelineResult:
    """Run a single pipeline and return results."""
    start_time = asyncio.get_event_loop().time()
    
    retrieval_start = asyncio.get_event_loop().time()
    await generator.retriever.query_processor.process(query)
    retrieval_results = await generator.retriever.retrieve(query)
    retrieval_latency_ms = int((asyncio.get_event_loop().time() - retrieval_start) * 1000)
    
    context_assembler = generator.prompt_builder.__class__.__bases__[0]  # Hacky but okay for now
    context_assembler = context_assembler()
    context_assembler.assemble(retrieval_results)
    
    # Create pipeline run and generate
    config, pipeline_version_id = await generator._get_pipeline_config(pipeline_id)
    run_id = await generator._create_pipeline_run(
        pipeline_id, pipeline_version_id, query, [r.chunk_id for r in retrieval_results]
    )
    
    generation_start = asyncio.get_event_loop().time()
    result = await generator.generate(query, pipeline_id)
    int((asyncio.get_event_loop().time() - generation_start) * 1000)
    
    total_latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    
    # Enqueue evaluation
    asyncio.create_task(generator._enqueue_evaluation_job(run_id))
    
    return PipelineResult(
        run_id=result.run_id,
        generation=result.full_response,
        retrieval_latency_ms=retrieval_latency_ms,
        total_latency_ms=total_latency_ms,
        chunks_used=len(retrieval_results),
        eval_score=None  # Will be available later via evaluation run
    )


@router.post("/compare")
async def compare_pipelines(request: CompareRequest) -> dict[str, Any]:
    try:
        pipeline_a_id = uuid.UUID(request.pipeline_a_id)
        pipeline_b_id = uuid.UUID(request.pipeline_b_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline ID")
    
    generator = Generator()
    
    # Run both pipelines in parallel
    task_a = run_pipeline(generator, request.query, pipeline_a_id)
    task_b = run_pipeline(generator, request.query, pipeline_b_id)
    
    result_a, result_b = await asyncio.gather(task_a, task_b)
    
    return {
        "query": request.query,
        "pipeline_a": {
            "run_id": result_a.run_id,
            "generation": result_a.generation,
            "retrieval_latency_ms": result_a.retrieval_latency_ms,
            "total_latency_ms": result_a.total_latency_ms,
            "chunks_used": result_a.chunks_used,
            "eval_score": result_a.eval_score
        },
        "pipeline_b": {
            "run_id": result_b.run_id,
            "generation": result_b.generation,
            "retrieval_latency_ms": result_b.retrieval_latency_ms,
            "total_latency_ms": result_b.total_latency_ms,
            "chunks_used": result_b.chunks_used,
            "eval_score": result_b.eval_score
        }
    }
