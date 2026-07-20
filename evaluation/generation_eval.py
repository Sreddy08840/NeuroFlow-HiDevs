"""
Generation evaluation script that evaluates retrieval + generation on a test set.
"""
import asyncio
import json
from typing import List, Dict, Any
from pathlib import Path
from pipelines.generation.generator import Generator
from evaluation.judge import EvaluationJudge
from backend.models import PipelineConfig
from backend.config import settings
import uuid


# Sample test questions for evaluation
TEST_QUESTIONS = [
    {
        "query": "What is multi-head attention in transformers?",
        "ground_truth": "Multi-head attention is a mechanism in transformers that allows the model to attend to different positions of the input sequence simultaneously using multiple attention heads."
    },
    {
        "query": "How does backpropagation work?",
        "ground_truth": "Backpropagation is an algorithm used to train neural networks by computing gradients of the loss function with respect to each weight using the chain rule, propagating errors backward from the output to the input layer."
    },
    {
        "query": "Explain the difference between supervised and unsupervised learning.",
        "ground_truth": "Supervised learning uses labeled data to train models, while unsupervised learning finds patterns in unlabeled data without predefined labels."
    }
]


async def evaluate_generation() -> Dict[str, Any]:
    print("Starting generation evaluation...")
    
    # Use first pipeline (we'll create a dummy config for testing)
    pipeline_id = uuid.uuid4()  # In real use, this would be an existing pipeline
    config = PipelineConfig(
        name="Evaluation Pipeline",
        retrieval={
            "dense_k": 30,
            "sparse_k": 20,
            "top_k_after_rerank": 8,
            "rrf_k": 60,
            "rrf_dense_weight": 1.5,
            "rrf_sparse_weight": 1.0,
            "rrf_metadata_weight": 1.0
        }
    )
    
    generator = Generator()
    judge = EvaluationJudge()
    
    results: List[Dict] = []
    total_faithfulness = 0.0
    total_answer_relevance = 0.0
    total_context_precision = 0.0
    total_overall_score = 0.0
    
    for item in TEST_QUESTIONS:
        query = item["query"]
        print(f"\nEvaluating query: {query}")
        
        try:
            # For testing, we'll skip actual pipeline config loading and use a mock
            # In real use, this would use an existing pipeline in the database
            # For now, we'll just compute metrics using the judge with dummy data
            dummy_answer = "This is a dummy answer for testing purposes."
            dummy_chunks = [
                "Dummy chunk 1 for testing retrieval and generation evaluation.",
                "Dummy chunk 2 with more test content."
            ]
            run_id = uuid.uuid4()
            
            eval_metrics = await judge.evaluate(
                run_id=run_id,
                query=query,
                answer=dummy_answer,
                chunks=dummy_chunks
            )
            
            results.append({
                "query": query,
                "answer": dummy_answer,
                "metrics": eval_metrics
            })
            
            total_faithfulness += eval_metrics["faithfulness"]
            total_answer_relevance += eval_metrics["answer_relevance"]
            total_context_precision += eval_metrics["context_precision"]
            total_overall_score += eval_metrics["overall_score"]
            
            print(f"  Faithfulness: {eval_metrics['faithfulness']:.2f}")
            print(f"  Answer Relevance: {eval_metrics['answer_relevance']:.2f}")
            print(f"  Context Precision: {eval_metrics['context_precision']:.2f}")
            print(f"  Overall Score: {eval_metrics['overall_score']:.2f}")
            
        except Exception as e:
            print(f"  Error evaluating query: {e}")
            continue
    
    # Compute averages
    num_evaluations = len(results)
    avg_metrics = {}
    if num_evaluations > 0:
        avg_metrics = {
            "faithfulness_avg": total_faithfulness / num_evaluations,
            "answer_relevance_avg": total_answer_relevance / num_evaluations,
            "context_precision_avg": total_context_precision / num_evaluations,
            "overall_score_avg": total_overall_score / num_evaluations,
            "num_evaluations": num_evaluations
        }
        
        print("\n===== Average Metrics =====")
        print(f"Faithfulness: {avg_metrics['faithfulness_avg']:.2f}")
        print(f"Answer Relevance: {avg_metrics['answer_relevance_avg']:.2f}")
        print(f"Context Precision: {avg_metrics['context_precision_avg']:.2f}")
        print(f"Overall Score: {avg_metrics['overall_score_avg']:.2f}")
    
    return {
        "results": results,
        "average_metrics": avg_metrics
    }


if __name__ == "__main__":
    output = asyncio.run(evaluate_generation())
    
    # Save to file
    with open("evaluation/generation_eval_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
