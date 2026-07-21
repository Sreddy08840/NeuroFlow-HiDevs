import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from backend.api.auth import require_scope
from pipelines.finetuning import Extractor, JobManager

router = APIRouter(prefix="/finetune", tags=["finetune"])


class CreateJobRequest(BaseModel):
    base_model: str | None = "gpt-4o-mini-2024-07-18"
    task_type: str | None = "rag_generation"


# Initialize dependencies
extractor = Extractor()
job_manager = JobManager()


async def run_job_polling(job_id: uuid.UUID, mlflow_run_id: str) -> None:
    """Background task to poll job status."""
    await job_manager.poll_job(job_id, mlflow_run_id)


@router.post("/jobs", dependencies=[Depends(require_scope("admin"))])
async def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    """Create and submit a new fine-tuning job."""
    try:
        job_id = await job_manager.submit_job(request.base_model, request.task_type)
        # Note: We'd need to store mlflow_run_id somewhere, for now use dummy
        background_tasks.add_task(run_job_polling, job_id, "dummy_run_id")
        return {"job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    """List all fine-tuning jobs."""
    return await job_manager.list_jobs()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Get detailed job info."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    
    job = await job_manager.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.get("/training-data/preview")
async def preview_training_data(limit: int = 5) -> list[dict[str, Any]]:
    """Preview sample training pairs without submitting a job."""
    return await extractor.preview(limit)
