import json
import math
from typing import List
from backend.providers import NeuroFlowClient, ChatMessage, RoutingCriteria


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


async def evaluate_answer_relevance(query: str, answer: str) -> float:
    client = NeuroFlowClient()

    if not query or not answer:
        return 0.0

    # Step 1: Generate 3-5 questions that this answer could respond to
    gen_questions_prompt = [
        ChatMessage(
            role="system",
            content="Generate 3-5 questions that the given answer would be a good response to. Return them as a JSON array of strings, no other text."
        ),
        ChatMessage(role="user", content=f"Answer: {answer}")
    ]
    try:
        questions_response = await client.chat(
            gen_questions_prompt,
            criteria=RoutingCriteria(task_type="evaluation")
        )
        questions_content = questions_response.content.strip()
        if questions_content.startswith("```json"):
            questions_content = questions_content.split("```json", 1)[1].split("```", 1)[0].strip()
        questions = json.loads(questions_content)
    except (json.JSONDecodeError, Exception):
        questions = []

    if not questions:
        return 0.0

    # Step 2: Embed original query and all generated questions
    texts_to_embed = [query] + questions
    embeddings = await client.embed(texts_to_embed)
    query_embedding = embeddings[0]
    question_embeddings = embeddings[1:]

    # Step 3: Compute average cosine similarity
    total_similarity = 0.0
    for q_emb in question_embeddings:
        total_similarity += cosine_similarity(query_embedding, q_emb)

    return total_similarity / len(question_embeddings)
