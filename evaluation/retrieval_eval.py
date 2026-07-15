import asyncio
import json
from dataclasses import dataclass
from typing import List, Dict, Any
from pipelines.retrieval import Retriever, RetrievalResult


@dataclass
class RetrievalMetrics:
    hit_rate: float
    mrr: float
    total_queries: int


async def evaluate_retrieval(
    retriever: Retriever,
    test_set: List[Dict[str, Any]],
    k: int = 10
) -> RetrievalMetrics:
    total_hits = 0
    total_reciprocal_rank = 0.0

    for test in test_set:
        query = test["query"]
        relevant_ids = set(test["relevant_chunk_ids"])

        results = await retriever.retrieve(query, k=k)
        result_ids = [r.chunk_id for r in results]

        # Calculate hit
        hit = any(chunk_id in relevant_ids for chunk_id in result_ids)
        if hit:
            total_hits += 1

        # Calculate MRR
        rank = None
        for idx, chunk_id in enumerate(result_ids):
            if chunk_id in relevant_ids:
                rank = idx + 1
                break
        if rank:
            total_reciprocal_rank += 1.0 / rank

    hit_rate = total_hits / len(test_set) if test_set else 0.0
    mrr = total_reciprocal_rank / len(test_set) if test_set else 0.0

    return RetrievalMetrics(
        hit_rate=hit_rate,
        mrr=mrr,
        total_queries=len(test_set)
    )


if __name__ == "__main__":
    # Example test set (replace with real data once you have chunks loaded)
    test_set = [
        {
            "query": "What is HNSW indexing?",
            "relevant_chunk_ids": []
        }
    ]

    async def main():
        retriever = Retriever()
        metrics = await evaluate_retrieval(retriever, test_set, k=10)

        print(f"Hit Rate: {metrics.hit_rate:.4f}")
        print(f"MRR: {metrics.mrr:.4f}")
        print(f"Total Queries: {metrics.total_queries}")

        # Save results to retrieval_results.json
        results_data = {
            "hit_rate": metrics.hit_rate,
            "mrr": metrics.mrr,
            "total_queries": metrics.total_queries,
            "test_set": test_set
        }
        with open("evaluation/retrieval_results.json", "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)

    asyncio.run(main())
