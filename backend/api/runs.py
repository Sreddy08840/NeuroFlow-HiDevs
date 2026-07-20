from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import uuid
import asyncpg
from backend.db.pool import get_db_pool


router = APIRouter(prefix="/runs", tags=["runs"])


class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Human evaluation of the answer quality, 1 (worst) to 5 (best)")


@router.patch(
    "/{run_id}/rating",
    tags=["Runs"],
    summary="Add human rating to run",
    description="Submit a human quality rating for a query run. Used for model calibration and evaluation."
)
async def update_run_rating(
    run_id: str = Field(..., description="ID of the query run to rate"),
    request: RatingRequest = ...
):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if there's an evaluation for this run
        evaluation = await conn.fetchrow("""
            SELECT id, overall_score, user_rating, metadata
            FROM evaluations WHERE run_id = $1
        """, run_uuid)

        if evaluation:
            # Update existing evaluation
            metadata = evaluation["metadata"] or {}
            # Check if both automated and human ratings exist
            if evaluation["overall_score"] is not None:
                human_score = request.rating / 5.0
                if abs(evaluation["overall_score"] - human_score) > 0.3:
                    metadata["calibration_needed"] = True
            await conn.execute("""
                UPDATE evaluations
                SET user_rating = $1, metadata = $2
                WHERE id = $3
            """, request.rating, metadata, evaluation["id"])
        else:
            # Create a new evaluation with just user rating (unlikely, but possible)
            eval_id = uuid.uuid4()
            await conn.execute("""
                INSERT INTO evaluations (
                    id, run_id, user_rating
                ) VALUES ($1, $2, $3)
            """, eval_id, run_uuid, request.rating)

    return {"status": "ok"}
