from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime, timedelta
from backend.db.pool import get_db_pool
from backend.models import PipelineConfig

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class CreatePipelineRequest(BaseModel):
    config: PipelineConfig


class UpdatePipelineRequest(BaseModel):
    config: Optional[PipelineConfig] = None
    description: Optional[str] = None


@router.post("", response_model=Dict[str, uuid.UUID])
async def create_pipeline(request: CreatePipelineRequest):
    config_dict = request.config.model_dump()
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Create pipeline entry
            pipeline_id = await conn.fetchval(
                """
                INSERT INTO pipelines (name, description)
                VALUES ($1, $2)
                RETURNING id
                """,
                config_dict["name"],
                config_dict.get("description")
            )
            # Create first version
            await conn.execute(
                """
                INSERT INTO pipeline_versions (pipeline_id, version, config)
                VALUES ($1, 1, $2)
                """,
                pipeline_id,
                json.dumps(config_dict)
            )
    return {"pipeline_id": pipeline_id}


@router.get("", response_model=List[Dict[str, Any]])
async def list_pipelines():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        pipelines = await conn.fetch(
            """
            SELECT 
                p.id, 
                p.name, 
                p.description, 
                p.status, 
                p.current_version,
                p.created_at,
                p.updated_at,
                (SELECT COUNT(*) FROM pipeline_runs pr WHERE pr.pipeline_id = p.id) AS total_runs,
                (SELECT AVG(latency_ms) FROM pipeline_runs pr WHERE pr.pipeline_id = p.id) AS avg_latency_ms
            FROM pipelines p
            WHERE p.status != 'archived'
            ORDER BY p.created_at DESC
            """
        )
        result = []
        for p in pipelines:
            row = dict(p)
            row["id"] = str(row["id"])
            result.append(row)
        return result


@router.get("/{pipeline_id}", response_model=Dict[str, Any])
async def get_pipeline(pipeline_id: str):
    try:
        pid = uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline ID")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get pipeline and current version
        pipeline = await conn.fetchrow(
            """
            SELECT p.*, pv.config
            FROM pipelines p
            JOIN pipeline_versions pv ON p.id = pv.pipeline_id AND p.current_version = pv.version
            WHERE p.id = $1
            """,
            pid
        )
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # Get aggregate evaluation scores
        eval_scores = await conn.fetchrow(
            """
            SELECT 
                AVG(faithfulness) AS avg_faithfulness,
                AVG(answer_relevance) AS avg_answer_relevance,
                AVG(context_precision) AS avg_context_precision,
                AVG(context_recall) AS avg_context_recall,
                AVG(overall_score) AS avg_overall_score
            FROM evaluations e
            JOIN pipeline_runs pr ON e.run_id = pr.id
            WHERE pr.pipeline_id = $1
            """,
            pid
        )
        
        result = dict(pipeline)
        result["id"] = str(result["id"])
        result["config"] = json.loads(result["config"])
        result["avg_scores"] = dict(eval_scores) if eval_scores else None
        return result


@router.patch("/{pipeline_id}")
async def update_pipeline(pipeline_id: str, request: UpdatePipelineRequest):
    try:
        pid = uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline ID")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Get current pipeline
            pipeline = await conn.fetchrow(
                "SELECT current_version FROM pipelines WHERE id = $1",
                pid
            )
            if not pipeline:
                raise HTTPException(status_code=404, detail="Pipeline not found")
            
            new_version = pipeline["current_version"] + 1
            # Update description if provided
            if request.description:
                await conn.execute(
                    """
                    UPDATE pipelines 
                    SET description = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    request.description,
                    pid
                )
            
            # Update config if provided (create new version)
            if request.config:
                config_dict = request.config.model_dump()
                await conn.execute(
                    """
                    INSERT INTO pipeline_versions (pipeline_id, version, config)
                    VALUES ($1, $2, $3)
                    """,
                    pid,
                    new_version,
                    json.dumps(config_dict)
                )
                await conn.execute(
                    """
                    UPDATE pipelines
                    SET current_version = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    new_version,
                    pid
                )
    return {"status": "ok"}


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    try:
        pid = uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline ID")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE pipelines SET status = 'archived', updated_at = NOW() WHERE id = $1",
            pid
        )
    return {"status": "ok"}


@router.get("/{pipeline_id}/runs", response_model=List[Dict[str, Any]])
async def list_pipeline_runs(
    pipeline_id: str, 
    limit: int = 20, 
    offset: int = 0
):
    try:
        pid = uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline ID")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        runs = await conn.fetch(
            """
            SELECT pr.*, e.overall_score
            FROM pipeline_runs pr
            LEFT JOIN evaluations e ON pr.id = e.run_id
            WHERE pr.pipeline_id = $1
            ORDER BY pr.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            pid,
            limit,
            offset
        )
        result = []
        for r in runs:
            row = dict(r)
            row["id"] = str(row["id"])
            row["pipeline_id"] = str(row["pipeline_id"])
            row["pipeline_version_id"] = str(row["pipeline_version_id"]) if row["pipeline_version_id"] else None
            result.append(row)
        return result


@router.get("/{pipeline_id}/analytics", response_model=Dict[str, Any])
async def get_pipeline_analytics(pipeline_id: str):
    try:
        pid = uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pipeline ID")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get latency percentiles
        latency = await conn.fetchrow(
            """
            SELECT 
                percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
                percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_latency_ms,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY retrieval_latency_ms) AS p50_retrieval_ms,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY generation_latency_ms) AS p50_generation_ms
            FROM pipeline_runs
            WHERE pipeline_id = $1
            """,
            pid
        )
        
        # Get average evaluation scores
        eval_scores = await conn.fetchrow(
            """
            SELECT 
                AVG(faithfulness) AS avg_faithfulness,
                AVG(answer_relevance) AS avg_answer_relevance,
                AVG(context_precision) AS avg_context_precision,
                AVG(context_recall) AS avg_context_recall,
                AVG(overall_score) AS avg_overall_score
            FROM evaluations e
            JOIN pipeline_runs pr ON e.run_id = pr.id
            WHERE pr.pipeline_id = $1
            """,
            pid
        )
        
        # Get queries per day for last 30 days
        queries_per_day = await conn.fetch(
            """
            SELECT 
                DATE(created_at) AS day, 
                COUNT(*) AS count
            FROM pipeline_runs
            WHERE pipeline_id = $1
              AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY day
            ORDER BY day
            """,
            pid
        )
        
        return {
            "latency": dict(latency) if latency else None,
            "evaluation_scores": dict(eval_scores) if eval_scores else None,
            "queries_per_day": [{"day": str(d["day"]), "count": d["count"]} for d in queries_per_day]
        }
