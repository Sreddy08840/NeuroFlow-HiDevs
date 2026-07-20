import asyncio
import json
from typing import Any, List
import asyncpg
from opentelemetry import trace
from opentelemetry.trace import Tracer
from .base import RetrievalResult, ProcessedQuery
from .fusion import reciprocal_rank_fusion
from .query_processor import QueryProcessor
from .reranker import Reranker
from backend.providers import NeuroFlowClient
from backend.db.pool import get_db_pool
from backend.config import settings
from backend.monitoring.metrics import retrieval_latency


tracer: Tracer = trace.get_tracer(__name__)


class Retriever:
    def __init__(
        self,
        db_pool: asyncpg.Pool | None = None,
        client: NeuroFlowClient | None = None,
        query_processor: QueryProcessor | None = None,
        reranker: Reranker | None = None
    ):
        self.db_pool = db_pool
        self.client = client or NeuroFlowClient()
        self.query_processor = query_processor or QueryProcessor(self.client)
        self.reranker = reranker or Reranker(self.client)

    async def _get_db_pool(self):
        if self.db_pool is None:
            self.db_pool = await get_db_pool()
        return self.db_pool

    async def retrieve(
        self,
        query: str,
        k: int = 20,
        use_rerank: bool = True,
        dense_k: int = 30,
        sparse_k: int = 20,
        rrf_k: int = 60,
        rrf_dense_weight: float = 1.0,
        rrf_sparse_weight: float = 1.0,
        rrf_metadata_weight: float = 1.0
    ) -> List[RetrievalResult]:
        import time
        start_time = time.time()
        
        with tracer.start_as_current_span("retrieval.pipeline") as pipeline_span:
            # Step 1: Process query
            processed = await self.query_processor.process(query)

            # Step 2: Run parallel retrievals
            async def _dense_with_span():
                with tracer.start_as_current_span("retrieval.dense") as dense_span:
                    results = await self._dense_retrieval(processed, dense_k)
                    dense_span.set_attributes({"chunk_count": len(results)})
                    return results
            
            async def _sparse_with_span():
                with tracer.start_as_current_span("retrieval.sparse") as sparse_span:
                    results = await self._sparse_retrieval(processed, sparse_k)
                    sparse_span.set_attributes({"chunk_count": len(results)})
                    return results
            
            async def _metadata_with_span():
                with tracer.start_as_current_span("retrieval.metadata") as metadata_span:
                    results = await self._metadata_retrieval(processed, sparse_k)
                    metadata_span.set_attributes({"chunk_count": len(results)})
                    return results

            dense_results, sparse_results, metadata_results = await asyncio.gather(
                _dense_with_span(),
                _sparse_with_span(),
                _metadata_with_span()
            )

            # Step 3: Fuse results with span
            with tracer.start_as_current_span("retrieval.fusion") as fusion_span:
                all_results = [dense_results, sparse_results, metadata_results]
                weights = [rrf_dense_weight, rrf_sparse_weight, rrf_metadata_weight]
                # Filter out empty result lists and adjust weights accordingly
                filtered_results = []
                filtered_weights = []
                for res, w in zip(all_results, weights):
                    if len(res) > 0:
                        filtered_results.append(res)
                        filtered_weights.append(w)
                fused = reciprocal_rank_fusion(filtered_results, k=rrf_k, weights=filtered_weights)
                fusion_span.set_attributes({"chunk_count": len(fused)})

            # Step 4: Rerank with span
            if use_rerank:
                with tracer.start_as_current_span("retrieval.rerank") as rerank_span:
                    fused = await self.reranker.rerank(processed.original, fused, top_k=40)
                    rerank_span.set_attributes({"chunk_count": len(fused)})

            pipeline_span.set_attributes({"query": query, "k": k})
            
            # Record retrieval latency
            retrieval_latency.labels(strategy="combined").observe(time.time() - start_time)

            # Take top k
            return fused[:k]

    async def _dense_retrieval(
        self,
        processed: ProcessedQuery,
        k: int
    ) -> List[RetrievalResult]:
        pool = await self._get_db_pool()
        # Get embedding for original query
        all_queries = [processed.original] + processed.expanded
        # Embed all queries in batch
        embeddings = await self.client.embed(all_queries)

        all_chunks: set[str] = set()
        results: List[RetrievalResult] = []

        async with pool.acquire() as conn:
            for idx, embedding in enumerate(embeddings):
                # Search pgvector
                records = await conn.fetch(
                    """
                    SELECT
                        id AS chunk_id,
                        document_id,
                        content,
                        metadata,
                        (embedding <=> $1) AS distance
                    FROM chunks
                    ORDER BY embedding <=> $1
                    LIMIT $2
                    """,
                    embedding,
                    k
                )
                for rank, rec in enumerate(records, 1):
                    chunk_id = rec["chunk_id"]
                    if chunk_id not in all_chunks:
                        all_chunks.add(chunk_id)
                        results.append(RetrievalResult(
                            chunk_id=chunk_id,
                            document_id=rec["document_id"],
                            content=rec["content"],
                            metadata=rec["metadata"] or {},
                            score=1.0 / (1 + rec["distance"]),
                            rank=rank
                        ))

        # Sort by score and take top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    async def _sparse_retrieval(
        self,
        processed: ProcessedQuery,
        k: int
    ) -> List[RetrievalResult]:
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT
                    id AS chunk_id,
                    document_id,
                    content,
                    metadata,
                    ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', $1)) AS score
                FROM chunks
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                ORDER BY score DESC
                LIMIT $2
                """,
                processed.original,
                k
            )
            results = []
            for rank, rec in enumerate(records, 1):
                results.append(RetrievalResult(
                    chunk_id=rec["chunk_id"],
                    document_id=rec["document_id"],
                    content=rec["content"],
                    metadata=rec["metadata"] or {},
                    score=rec["score"],
                    rank=rank
                ))
            return results

    async def _metadata_retrieval(
        self,
        processed: ProcessedQuery,
        k: int
    ) -> List[RetrievalResult]:
        if not processed.metadata_filter:
            return []
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            # First get query embedding
            query_embedding = (await self.client.embed([processed.original]))[0]
            records = await conn.fetch(
                """
                SELECT
                    id AS chunk_id,
                    document_id,
                    content,
                    metadata,
                    (embedding <=> $1) AS distance
                FROM chunks
                WHERE metadata @> $2::jsonb
                ORDER BY embedding <=> $1
                LIMIT $3
                """,
                query_embedding,
                json.dumps(processed.metadata_filter),
                k
            )
            results = []
            for rank, rec in enumerate(records, 1):
                results.append(RetrievalResult(
                    chunk_id=rec["chunk_id"],
                    document_id=rec["document_id"],
                    content=rec["content"],
                    metadata=rec["metadata"] or {},
                    score=1.0 / (1 + rec["distance"]),
                    rank=rank
                ))
            return results
