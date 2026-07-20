"""
Automated hyperparameter search for retrieval metrics.
Tests combinations of dense_k, sparse_k, top_k_after_rerank, and rrf_k.
"""
import asyncio
import json
import itertools
from typing import List, Dict, Any
from pathlib import Path


# Hyperparameter search space
SEARCH_SPACE = {
    "dense_k": [10, 20, 30],
    "sparse_k": [10, 15, 20],
    "top_k_after_rerank": [5, 8, 10],
    "rrf_k": [30, 60, 120]
}


def generate_combinations(search_space: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Generate all combinations of hyperparameters from search space."""
    keys = list(search_space.keys())
    values = list(search_space.values())
    combinations = list(itertools.product(*values))
    return [dict(zip(keys, combo)) for combo in combinations]


async def evaluate_combination(params: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a single combination of hyperparameters (placeholder for real evaluation)."""
    # In real use, this would use the Retriever to compute real Hit@10 and MRR@10
    # For demo purposes, we'll use synthetic scores based on params
    mrr = 0.5 + (params["dense_k"] / 100) + (params["rrf_k"] / 500)
    hit_rate = 0.7 + (params["dense_k"] / 200) + (params["sparse_k"] / 200)
    
    return {
        "params": params,
        "mrr_at_10": min(mrr, 0.85),
        "hit_rate_at_10": min(hit_rate, 0.9)
    }


async def run_hyperparameter_search() -> None:
    print("Starting hyperparameter search...")
    
    # Generate all combinations
    combinations = generate_combinations(SEARCH_SPACE)
    print(f"Generated {len(combinations)} hyperparameter combinations to test")
    
    # Evaluate all combinations
    results: List[Dict] = []
    for idx, params in enumerate(combinations):
        print(f"Evaluating combination {idx + 1}/{len(combinations)}: {params}")
        result = await evaluate_combination(params)
        results.append(result)
        print(f"  MRR@10: {result['mrr_at_10']:.4f}, Hit@10: {result['hit_rate_at_10']:.4f}")
    
    # Find best combination by MRR@10
    results.sort(key=lambda x: x["mrr_at_10"], reverse=True)
    best = results[0]
    print("\n===== Best Combination =====")
    print(f"Params: {best['params']}")
    print(f"MRR@10: {best['mrr_at_10']:.4f}")
    print(f"Hit Rate@10: {best['hit_rate_at_10']:.4f}")
    
    # Save all results
    output_path = Path(__file__).parent / "hyperparameter_search_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "search_space": SEARCH_SPACE,
            "all_results": results,
            "best_result": best
        }, f, indent=2)
    
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(run_hyperparameter_search())
