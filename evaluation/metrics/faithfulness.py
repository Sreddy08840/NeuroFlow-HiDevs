import json
from typing import Optional
from backend.providers import NeuroFlowClient, ChatMessage, RoutingCriteria


async def evaluate_faithfulness(query: str, answer: str, context: str) -> float:
    client = NeuroFlowClient()

    if not answer or not context:
        return 0.0

    # Step 1: Extract claims from answer
    extract_claims_prompt = [
        ChatMessage(
            role="system",
            content="Extract all factual claims from the answer as a JSON array of strings. Only include factual statements, no opinions. Return only the JSON array, no other text."
        ),
        ChatMessage(role="user", content=f"Answer: {answer}")
    ]
    try:
        claims_response = await client.chat(
            extract_claims_prompt,
            criteria=RoutingCriteria(task_type="evaluation")
        )
        claims_content = claims_response.content.strip()
        if claims_content.startswith("```json"):
            claims_content = claims_content.split("```json", 1)[1].split("```", 1)[0].strip()
        claims = json.loads(claims_content)
    except (json.JSONDecodeError, Exception):
        claims = []

    if not claims:
        return 0.0

    # Step 2: Evaluate each claim
    total_score = 0.0
    for claim in claims:
        evaluate_claim_prompt = [
            ChatMessage(
                role="system",
                content="Determine if the claim is supported by the context. Answer only with one of: yes, no, partial."
            ),
            ChatMessage(
                role="user",
                content=f"Context:\n{context}\n\nClaim:\n{claim}"
            )
        ]
        try:
            evaluation_response = await client.chat(
                evaluate_claim_prompt,
                criteria=RoutingCriteria(task_type="evaluation")
            )
            evaluation = evaluation_response.content.strip().lower()
            if evaluation == "yes":
                total_score += 1.0
            elif evaluation == "partial":
                total_score += 0.5
            elif evaluation == "no":
                total_score += 0.0
        except Exception:
            total_score += 0.0

    return total_score / len(claims)
