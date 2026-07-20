"""Data models for NeuroFlow API responses."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Document(BaseModel):
    """Represents an ingested document in NeuroFlow."""
    id: str = Field(..., description="Unique identifier for the document")
    filename: str = Field(..., description="Name of the ingested file")
    status: str = Field(..., description="Current status of the document (e.g., 'ingested', 'processing')")
    pipeline_id: Optional[str] = Field(None, description="Pipeline ID this document was ingested into")
    created_at: datetime = Field(..., description="Timestamp when the document was created")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the document")


class Citation(BaseModel):
    """A citation from a query response linking to a source document."""
    reference: str = Field(..., description="Reference marker used in the answer, e.g., [Source 1]")
    chunk_id: str = Field(..., description="ID of the cited chunk")
    document: Optional[str] = Field(None, description="Name of the source document")
    page: Optional[int] = Field(None, description="Page number in the source document")


class QueryResult(BaseModel):
    """Result from a RAG query."""
    run_id: str = Field(..., description="Unique identifier for this query run")
    answer: str = Field(..., description="The generated answer to the query")
    citations: List[Citation] = Field(default_factory=list, description="Citations used in the answer")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="List of sources retrieved")


class EvaluationResult(BaseModel):
    """Evaluation metrics for a query run."""
    run_id: str = Field(..., description="Unique identifier for the evaluated query run")
    faithfulness: float = Field(..., ge=0, le=1, description="How faithful the answer is to the context (0-1)")
    answer_relevance: float = Field(..., ge=0, le=1, description="How relevant the answer is to the query (0-1)")
    context_precision: float = Field(..., ge=0, le=1, description="Precision of retrieved context (0-1)")
    context_recall: float = Field(..., ge=0, le=1, description="Recall of retrieved context (0-1)")
    overall_score: float = Field(..., ge=0, le=1, description="Combined overall evaluation score (0-1)")
    evaluated_at: datetime = Field(..., description="Timestamp when evaluation was completed")
