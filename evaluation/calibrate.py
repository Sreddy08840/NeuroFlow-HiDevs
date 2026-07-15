import asyncio
import json
from typing import List, Dict
from scipy.stats import pearsonr
from evaluation.metrics.faithfulness import evaluate_faithfulness


async def run_calibration() -> None:
    # Load annotated set
    with open("evaluation/calibration/annotated_set.json", "r", encoding="utf-8") as f:
        annotated_set: List[Dict] = json.load(f)

    if not annotated_set:
        print("Annotated set is empty!")
        return

    # Evaluate each item
    human_scores = []
    automated_scores = []

    for item in annotated_set:
        query = item["query"]
        answer = item["answer"]
        context = item["context"]
        human_faithfulness = item["human_faithfulness"]

        automated_faithfulness = await evaluate_faithfulness(query, answer, context)

        human_scores.append(human_faithfulness)
        automated_scores.append(automated_faithfulness)

    # Compute Pearson correlation
    if len(human_scores) >= 2:
        corr, p_value = pearsonr(human_scores, automated_scores)
        results = {
            "pearson_correlation": corr,
            "p_value": p_value,
            "num_samples": len(human_scores)
        }
        print(f"Pearson correlation: {corr:.4f}")
        print(f"P-value: {p_value:.4f}")

        with open("evaluation/calibration_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    else:
        print("Not enough samples to compute correlation!")


if __name__ == "__main__":
    asyncio.run(run_calibration())
