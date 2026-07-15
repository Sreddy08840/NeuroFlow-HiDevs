import re
from typing import List
from backend.providers import NeuroFlowClient, ChatMessage, RoutingCriteria


def split_into_sentences(text: str) -> List[str]:
    # Simple sentence splitter, can be improved
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences


async def evaluate_context_recall(query: str, chunks: List[str], answer: str) -> float:
    client = NeuroFlowClient()

    context = "\n\n".join(chunks)
    sentences = split_into_sentences(answer)

    if not sentences or not context:
        return 0.0

    # Step 1: Evaluate each sentence
    attributable_count = 0
    for sentence in sentences:
        evaluate_sentence_prompt = [
            ChatMessage(
                role="system",
                content="Can this sentence be attributed to the provided context? Answer only yes or no, lowercase."
            ),
            ChatMessage(
                role="user",
                content=f"Context:\n{context}\n\nSentence:\n{sentence}"
            )
        ]
        try:
            evaluation_response = await client.chat(
                evaluate_sentence_prompt,
                criteria=RoutingCriteria(task_type="evaluation")
            )
            evaluation = evaluation_response.content.strip().lower()
            if evaluation == "yes":
                attributable_count += 1
        except Exception:
            continue

    return attributable_count / len(sentences)
