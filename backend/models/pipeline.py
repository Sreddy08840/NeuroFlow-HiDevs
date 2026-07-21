from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IngestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunking_strategy: Literal["fixed", "semantic", "hierarchical"] = Field(
        default="fixed", description="Strategy for splitting documents into chunks"
    )
    chunk_size_tokens: int = Field(default=400, ge=100, le=2000, description="Target chunk size in tokens")
    chunk_overlap_tokens: int = Field(default=80, ge=0, le=400, description="Overlap between consecutive chunks in tokens")
    extractors_enabled: list[Literal["pdf", "docx", "image", "csv", "url", "text"]] = Field(
        default_factory=lambda: ["pdf", "docx", "image", "csv", "url", "text"],
        description="List of file types supported for ingestion"
    )


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dense_k: int = Field(default=30, ge=1, le=100, description="Number of dense retrieval results to fetch")
    sparse_k: int = Field(default=20, ge=1, le=100, description="Number of sparse retrieval results to fetch")
    reranker: Literal["cross-encoder", "none"] | None = Field(default="cross-encoder", description="Reranking model to use")
    top_k_after_rerank: int = Field(default=8, ge=1, le=20, description="Number of top chunks to keep after reranking")
    query_expansion: bool = Field(default=True, description="Whether to expand queries with synonyms/related terms")
    metadata_filters_enabled: bool = Field(default=True, description="Enable filtering by document metadata")
    rrf_k: int = Field(default=60, ge=1, le=200, description="Reciprocal Rank Fusion k parameter")
    rrf_dense_weight: float = Field(default=1.0, ge=0.0, le=3.0, description="Weight for dense retrieval results in RRF")
    rrf_sparse_weight: float = Field(default=1.0, ge=0.0, le=3.0, description="Weight for sparse retrieval results in RRF")
    rrf_metadata_weight: float = Field(default=1.0, ge=0.0, le=3.0, description="Weight for metadata retrieval results in RRF")


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_routing: dict[str, str | float | int] = Field(
        default_factory=lambda: {"task_type": "rag_generation", "max_cost_per_call": 0.05},
        description="Configuration for model routing and cost control"
    )
    max_context_tokens: int = Field(default=6000, ge=1000, le=128000, description="Maximum tokens in context window")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="LLM temperature for generation")
    system_prompt_variant: Literal["precise", "concise", "detailed"] = Field(
        default="precise",
        description="Which system prompt variant to use"
    )


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_evaluate: bool = True
    training_threshold: float = Field(default=0.82, ge=0.0, le=1.0)


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
