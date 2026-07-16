import uuid
import mlflow
import mlflow.sklearn
from datetime import datetime
from typing import List, Dict, Any, Optional
from .extractor import TrainingPair
from statistics import mean


class MLflowTracker:
    def __init__(self, mlflow_tracking_uri: Optional[str] = None):
        if mlflow_tracking_uri:
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        mlflow.set_experiment("neuroflow-finetuning")

    def start_training_job(
        self,
        job_id: uuid.UUID,
        pairs: List[TrainingPair],
        base_model: str
    ) -> str:
        """Start MLflow run and log params/artifacts."""
        with mlflow.start_run(run_name=f"finetune-{job_id}") as run:
            # Log parameters
            mlflow.log_params({
                "job_id": str(job_id),
                "base_model": base_model,
                "training_pair_count": len(pairs),
                "avg_quality_score": mean([p.quality_score for p in pairs]) if pairs else 0.0,
                "min_date": str(datetime.now().date()),
                "max_date": str(datetime.now().date())
            })
            
            # Log training data
            mlflow.log_artifact(f"training_data/{job_id}.jsonl", artifact_path="training_data")
            
            return run.info.run_id

    def log_job_result(
        self,
        run_id: str,
        training_loss: Optional[float],
        validation_loss: Optional[float],
        trained_tokens: int
    ):
        """Log metrics after job completion."""
        with mlflow.start_run(run_id=run_id):
            if training_loss is not None:
                mlflow.log_metric("training_loss", training_loss)
            if validation_loss is not None:
                mlflow.log_metric("validation_loss", validation_loss)
            mlflow.log_metric("training_token_count", trained_tokens)

    def register_model(
        self,
        run_id: str,
        model_name: str
    ):
        """Register model in MLflow registry."""
        mlflow.register_model(f"runs:/{run_id}/model", model_name)
