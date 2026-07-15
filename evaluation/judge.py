import asyncio
import json
import uuid
from typing import Optional, Dict, Any
from opentelemetry import trace
import asyncpg
from backend.db.pool import get_db_pool
from backend.providers import NeuroFlowClient
from evaluation.metrics.faithfulness import evaluate_faithfulness
from evaluation.metrics.answer_relevance import evaluate_answer_relevance
from evaluation.metrics.context_precision import evaluate_context_precision
from evaluation.metrics.context_recall import evaluate_context_recall


tracer = trace.get_tracer(__name__)


class EvaluationJudge:
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        self.db_pool = db_pool
        self.client = NeuroFlowClient()

    async def _get_db_pool(self):
        if self.db_pool is None:
            self.db_pool = await get_db_pool()
        return self.db_pool

    async def evaluate(
        self,
        run_id: uuid.UUID,
        query: str,
        answer: str,
        chunks: list[str]
    ) -> Dict[str, Any]:
        with tracer.start_as_current_span("evaluation.judge") as span:
            # Run all four metrics in parallel
            context = "\n\n".join(chunks)
            faithfulness, answer_relevance, context_precision, context_recall = await asyncio.gather(
                evaluate_faithfulness(query, answer, context),
                evaluate_answer_relevance(query, answer),
                evaluate_context_precision(query, chunks, answer),
                evaluate_context_recall(query, chunks, answer)
            )

            # Compute overall score
            overall_score = (
                0.35 * faithfulness +
                0.30 * answer_relevance +
                0.20 * context_precision +
                0.15 * context_recall
            )

            # Update span attributes
            span.set_attributes({
                "faithfulness": faithfulness,
                "answer_relevance": answer_relevance,
                "context_precision": context_precision,
                "context_recall": context_recall,
                "overall_score": overall_score
            })

            # Write to evaluations table
            pool = await self._get_db_pool()
            judge_model = "gpt-4o"  # TODO: get from client response
            async with pool.acquire() as conn:
                evaluation_id = uuid.uuid4()
                await conn.execute("""
                    INSERT INTO evaluations (
                        id, run_id, faithfulness, answer_relevance,
                        context_precision, context_recall, overall_score,
                        judge_model
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, evaluation_id, run_id, faithfulness, answer_relevance,
                   context_precision, context_recall, overall_score, judge_model)

                # Check if overall score > 0.8, mark as training candidate
                if overall_score > 0.8:
                    # Get system prompt from somewhere? For now, placeholder
                    system_prompt = ""
                    training_pair_id = uuid.uuid4()
                    await conn.execute("""
                        INSERT INTO training_pairs (
                            id, run_id, system_prompt, user_message, assistant_message
                        ) VALUES ($1, $2, $3, $4, $5)
                    """, training_pair_id, run_id, system_prompt, query, answer)

            return {
                "faithfulness": faithfulness,
                "answer_relevance": answer_relevance,
                "context_precision": context_precision,
                "context_recall": context_recall,
                "overall_score": overall_score
            }
