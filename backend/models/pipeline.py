from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Literal


class IngestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunking_strategy: Literal["fixed", "semantic", "hierarchical"] = Field(
        default="fixed", description="Chunking strategy to use"
    )
    chunk_size_tokens: int = Field(default=400, ge=100, le=2000)
    chunk_overlap_tokens: int = Field(default=80, ge=0, le=400)
    extractors_enabled: List[Literal["pdf", "docx", "image", "csv", "url", "text"]] = Field(
        default_factory=lambda: ["pdf", "docx", "image", "csv", "url", "text"]
    )


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dense_k: int = Field(default=30, ge=1, le=100)
    sparse_k: int = Field(default=20, ge=1, le=100)
    reranker: Optional[Literal["cross-encoder", "none"]] = "cross-encoder"
    top_k_after_rerank: int = Field(default=8, ge=1, le=20)
    query_expansion: bool = True
    metadata_filters_enabled: bool = True
    rrf_k: int = Field(default=60, ge=1, le=200)
    rrf_dense_weight: float = Field(default=1.0, ge=0.0, le=3.0)
    rrf_sparse_weight: float = Field(default=1.0, ge=0.0, le=3.0)
    rrf_metadata_weight: float = Field(default=1.0, ge=0.0, le=3.0)


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_routing: Dict[str, str | float | int] = Field(
        default_factory=lambda: {"task_type": "rag_generation", "max_cost_per_call": 0.05}
    )
    max_context_tokens: int = Field(default=6000, ge=1000, le=128000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    system_prompt_variant: Literal["precise", "concise", "detailed"] = "precise"


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_evaluate: bool = True
    training_threshold: float = Field(default=0.82, ge=0.0, le=1.0)


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
