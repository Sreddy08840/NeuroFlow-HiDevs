import asyncio
from typing import List
from .base import RetrievalResult
from backend.providers import NeuroFlowClient, ChatMessage


class Reranker:
    def __init__(self, client: NeuroFlowClient | None = None):
        self.client = client or NeuroFlowClient()

    async def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        top_k: int = 40
    ) -> List[RetrievalResult]:
        if not candidates:
            return []
        # Take top 40 candidates
        candidates_subset = candidates[:top_k]

        # Score all pairs in parallel
        async def _score_candidate(candidate: RetrievalResult) -> tuple[RetrievalResult, float]:
            score = await self._score_pair(query, candidate.content)
            return candidate, score

        tasks = [_score_candidate(c) for c in candidates_subset]
        scored_pairs = await asyncio.gather(*tasks)

        # Sort by score descending
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        # Build final list with new ranks
        reranked = []
        for new_rank, (candidate, score) in enumerate(scored_pairs, 1):
            reranked.append(RetrievalResult(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                content=candidate.content,
                metadata=candidate.metadata,
                score=score,
                rank=new_rank
            ))

        return reranked

    async def _score_pair(self, query: str, passage: str) -> float:
        messages = [
            ChatMessage(role="system", content="You rate the relevance of a passage to a query on a scale from 0 to 10. Return only the number."),
            ChatMessage(role="user", content=f"Query: {query}\nPassage: {passage}")
        ]
        try:
            result = await self.client.chat(messages)
            content = result.content.strip()
            # Extract number from response
            import re
            match = re.search(r'\d+(\.\d+)?', content)
            if match:
                return float(match.group())
            return 0.0
        except Exception:
            return 0.0
