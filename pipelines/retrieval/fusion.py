from typing import Any
from collections import defaultdict
from .base import RetrievalResult


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievalResult]],
    k: int = 60
) -> list[RetrievalResult]:
    chunk_scores = defaultdict(float)
    chunk_info: dict[str, RetrievalResult] = {}

    # Iterate through each result list
    for result_list in result_lists:
        for idx, result in enumerate(result_list):
            rank = idx + 1
            score = 1.0 / (k + rank)
            chunk_scores[result.chunk_id] += score
            if result.chunk_id not in chunk_info:
                chunk_info[result.chunk_id] = result

    # Sort by score descending
    sorted_chunks = sorted(
        chunk_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Build final list with updated ranks and scores
    fused_results = []
    for new_rank, (chunk_id, total_score) in enumerate(sorted_chunks, 1):
        result = chunk_info[chunk_id]
        fused_results.append(RetrievalResult(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            content=result.content,
            metadata=result.metadata,
            score=total_score,
            rank=new_rank
        ))

    return fused_results
