import uuid
import asyncio
from typing import Optional, Dict, Any
import asyncpg
import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings
from openai import AsyncOpenAI
from backend.db.pool import get_db_pool
from backend.config import settings
from .extractor import Extractor
from .tracker import MLflowTracker


class JobManager:
    def __init__(
        self,
        db_pool: Optional[asyncpg.Pool] = None,
        redis_client: Optional[redis.Redis] = None,
        extractor: Optional[Extractor] = None,
        tracker: Optional[MLflowTracker] = None,
        openai_client: Optional[AsyncOpenAI] = None
    ):
        self.db_pool = db_pool
        self.redis_client = redis_client
        self.extractor = extractor or Extractor()
        self.tracker = tracker or MLflowTracker()
        self.openai_client = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def _get_db_pool(self):
        if self.db_pool is None:
            self.db_pool = await get_db_pool()
        return self.db_pool

    async def _create_job_record(
        self,
        job_id: uuid.UUID,
        base_model: str
    ):
        """Insert job into finetune_jobs table."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO finetune_jobs (id, base_model, status)
                VALUES ($1, $2, 'pending')
            """, job_id, base_model)

    async def _update_job_status(
        self,
        job_id: uuid.UUID,
        status: str,
        provider_job_id: Optional[str] = None,
        training_loss: Optional[float] = None,
        validation_loss: Optional[float] = None,
        trained_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update job status in finetune_jobs table."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE finetune_jobs
                SET 
                    status = $1,
                    provider_job_id = COALESCE($2, provider_job_id),
                    training_loss = COALESCE($3, training_loss),
                    validation_loss = COALESCE($4, validation_loss),
                    training_pair_count = COALESCE($5, training_pair_count),
                    completed_at = CASE WHEN $1 = 'succeeded' THEN NOW() ELSE completed_at END,
                    metadata = COALESCE($6, metadata)
                WHERE id = $7
            """, status, provider_job_id, training_loss, validation_loss, trained_tokens, metadata, job_id)

    async def _register_model(
        self,
        job_id: uuid.UUID,
        provider_job_id: str,
        task_type: str = "rag_generation"
    ):
        """Register new model in Redis router config."""
        redis_client = redis.from_url(settings.redis_url)
        # Get current router config
        router_config = await redis_client.get("router:models") or b"[]"
        models_list = list[dict]()
        if router_config:
            import json
            models_list = json.loads(router_config)
        
        # Add new model
        models_list.append({
            "model": provider_job_id,
            "task_type": task_type,
            "prefer_fine_tuned": True
        })
        
        await redis_client.set("router:models", json.dumps(models_list))

    async def submit_job(
        self,
        base_model: str = "gpt-4o-mini-2024-07-18",
        task_type: str = "rag_generation"
    ) -> uuid.UUID:
        """Extract training data, submit fine-tuning job, track in MLflow."""
        job_id = uuid.uuid4()
        
        # Create job record
        await self._create_job_record(job_id, base_model)
        
        # Extract training pairs
        pairs, pair_ids, jsonls = await self.extractor.extract(job_id)
        training_pair_count = len(pairs)
        
        if not pairs:
            await self._update_job_status(job_id, "failed", metadata={"reason": "No valid training pairs found"})
            raise ValueError("No valid training pairs found")
        
        # Update job with training pair count
        await self._update_job_status(
            job_id, "submitting", trained_tokens=training_pair_count * 1000  # Approximate
        )
        
        # Start MLflow run
        mlflow_run_id = self.tracker.start_training_job(job_id, pairs, base_model)
        
        # Upload training data to OpenAI
        jsonl_path = f"training_data/{job_id}.jsonl"
        with open(jsonl_path, "rb") as f:
            file_resp = await self.openai_client.files.create(
                file=f, purpose="fine-tune"
            )
        
        # Submit job to OpenAI
        openai_job = await self.openai_client.fine_tuning.jobs.create(
            training_file=file_resp.id, model=base_model
        )
        
        # Update job status and provider job id
        await self._update_job_status(
            job_id, "running", provider_job_id=openai_job.id
        )
        
        return job_id

    async def poll_job(
        self,
        job_id: uuid.UUID,
        mlflow_run_id: str
    ):
        """Poll OpenAI job status periodically."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            job_record = await conn.fetchrow("""
                SELECT id, provider_job_id FROM finetune_jobs WHERE id = $1
            """, job_id)
        
        if not job_record or not job_record["provider_job_id"]:
            return
        
        provider_job_id = job_record["provider_job_id"]
        
        while True:
            openai_job = await self.openai_client.fine_tuning.jobs.retrieve(provider_job_id)
            
            if openai_job.status in ["succeeded", "failed", "cancelled"]:
                if openai_job.status == "succeeded":
                    # Log metrics
                    # Get metrics from job events
                    training_loss = None
                    validation_loss = None
                    trained_tokens = openai_job.trained_tokens if hasattr(openai_job, "trained_tokens") else 0
                    
                    for event in openai_job.events:
                        if hasattr(event, "data"):
                            if "train_loss" in event.data:
                                training_loss = event.data["train_loss"]
                            if "valid_loss" in event.data:
                                validation_loss = event.data["valid_loss"]
                    
                    self.tracker.log_job_result(
                        mlflow_run_id, training_loss, validation_loss, trained_tokens
                    )
                    
                    # Register model
                    fine_tuned_model = openai_job.fine_tuned_model
                    if fine_tuned_model:
                        await self._register_model(job_id, fine_tuned_model)
                        self.tracker.register_model(mlflow_run_id, f"neuroflow-finetune-{job_id}")
                    
                    # Update job
                    await self._update_job_status(
                        job_id, "succeeded",
                        provider_job_id=fine_tuned_model,
                        training_loss=training_loss,
                        validation_loss=validation_loss,
                        trained_tokens=trained_tokens
                    )
                
                else:
                    await self._update_job_status(job_id, openai_job.status)
                
                break
            
            await asyncio.sleep(60)

    async def list_jobs(self) -> list[Dict[str, Any]]:
        """List all finetune jobs."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT id, base_model, status, provider_job_id, created_at, completed_at
                FROM finetune_jobs
                ORDER BY created_at DESC
            """)
        
        return [dict(r) for r in records]

    async def get_job(self, job_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get detailed job info."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT * FROM finetune_jobs WHERE id = $1
            """, job_id)
        
        if record:
            return dict(record)
        return None
