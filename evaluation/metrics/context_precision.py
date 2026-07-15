from typing import List
from backend.providers import NeuroFlowClient, ChatMessage, RoutingCriteria


async def evaluate_context_precision(query: str, chunks: List[str], answer: str) -> float:
    client = NeuroFlowClient()

    if not chunks or not answer:
        return 0.0

    # Step 1: Evaluate each chunk for usefulness
    useful_flags = []
    for chunk in chunks:
        evaluate_chunk_prompt = [
            ChatMessage(
                role="system",
                content="Was this passage useful in generating the answer? Answer only yes or no, lowercase."
            ),
            ChatMessage(
                role="user",
                content=f"Query: {query}\n\nAnswer: {answer}\n\nPassage: {chunk}"
            )
        ]
        try:
            evaluation_response = await client.chat(
                evaluate_chunk_prompt,
                criteria=RoutingCriteria(task_type="evaluation")
            )
            evaluation = evaluation_response.content.strip().lower()
            useful_flags.append(1.0 if evaluation == "yes" else 0.0)
        except Exception:
            useful_flags.append(0.0)

    # Step 2: Compute weighted score
    numerator = 0.0
    denominator = 0.0
    for i, (useful, _) in enumerate(zip(useful_flags, chunks), start=1):  # ranks are 1-based
        weight = 1.0 / i
        numerator += useful * weight
        denominator += weight

    if denominator == 0:
        return 0.0

    return numerator / denominator
