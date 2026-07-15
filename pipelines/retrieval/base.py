from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    rank: int = 0


@dataclass
class ProcessedQuery:
    original: str
    expanded: list[str] = field(default_factory=list)
    metadata_filter: dict[str, Any] = field(default_factory=dict)
    query_type: str = "factual"
