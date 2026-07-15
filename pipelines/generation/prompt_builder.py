from dataclasses import dataclass
from typing import List, Optional
from pipelines.retrieval import ContextWindow, ProcessedQuery
from backend.providers import ChatMessage


@dataclass
class AssembledPrompt:
    messages: List[ChatMessage]
    prompt_text: str
    query_type: str


class PromptBuilder:
    def __init__(self):
        self.base_system_prompt = (
            "You are a precise research assistant. Answer the user's question using ONLY the provided context. "
            "If the context does not contain enough information to answer fully, say so explicitly. "
            "For every factual claim, include a citation in the format [Source N]. "
            "Do not introduce information not present in the context."
        )
        self.query_type_additions = {
            "factual": "Provide a direct, concise answer. If multiple sources agree, cite all of them.",
            "analytical": "Analyze and synthesize across the provided sources. Identify agreements and contradictions.",
            "comparative": "Organize your response as a structured comparison. Use a table if appropriate.",
            "procedural": "Provide numbered steps. Each step must be cited."
        }

    def build(
        self,
        query: str,
        context_window: ContextWindow,
        processed_query: ProcessedQuery,
        use_chain_of_thought: bool = False
    ) -> AssembledPrompt:
        # Get query type specific addition
        query_type = processed_query.query_type
        type_addition = self.query_type_additions.get(query_type, "")
        full_system_prompt = f"{self.base_system_prompt}\n\n{type_addition}".strip()

        # Build context section
        context_section = f"<context>\n{context_window.content}\n</context>"

        # Build user message
        if use_chain_of_thought and query_type in ["analytical", "comparative"]:
            user_message = (
                f"First, think through your reasoning step by step inside <think> tags, then provide your final answer.\n\n"
                f"{context_section}\n\nQuestion: {query}"
            )
        else:
            user_message = f"{context_section}\n\nQuestion: {query}"

        messages = [
            ChatMessage(role="system", content=full_system_prompt),
            ChatMessage(role="user", content=user_message)
        ]

        return AssembledPrompt(
            messages=messages,
            prompt_text=f"{full_system_prompt}\n\n{user_message}",
            query_type=query_type
        )
