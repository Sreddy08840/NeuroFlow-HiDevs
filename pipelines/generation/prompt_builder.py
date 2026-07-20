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
        self.system_prompts = {
            "precise": (
                "You are a precise research assistant. Answer the user's question using ONLY the provided context. "
                "If the context does not contain enough information to answer fully, say so explicitly. "
                "For every factual claim, include a citation in the format [Source N]. "
                "Do not introduce information not present in the context."
            ),
            "concise": (
                "You are a concise research assistant. Answer only using the provided context, with citations [Source N]. "
                "Keep answers brief and to the point."
            ),
            "detailed": (
                "You are a detailed research assistant. Answer the question thoroughly using only the provided context. "
                "Include all relevant details and cite sources [Source N] for every claim."
            )
        }
        
        self.query_type_examples = {
            "factual": (
                "Example:\n"
                "Question: What is photosynthesis?\n"
                "Answer: Photosynthesis is the process by which plants convert light energy into chemical energy [Source 1]."
            ),
            "analytical": (
                "Example:\n"
                "Question: What are the trade-offs between CNNs and Transformers?\n"
                "Answer: CNNs are more parameter-efficient for grid data [Source 1], while Transformers excel at long-range dependencies [Source 2]."
            ),
            "comparative": (
                "Example:\n"
                "Question: Compare supervised and unsupervised learning.\n"
                "Answer: Supervised learning uses labeled data [Source 1], while unsupervised learning finds patterns in unlabeled data [Source 2]."
            ),
            "procedural": (
                "Example:\n"
                "Question: How to train a neural network?\n"
                "Answer:\n"
                "1. Prepare and preprocess the dataset [Source 1]\n"
                "2. Initialize model weights [Source 2]\n"
                "3. Train using backpropagation [Source 1]"
            )
        }

    def build(
        self,
        query: str,
        context_window: ContextWindow,
        processed_query: ProcessedQuery,
        use_chain_of_thought: bool = False,
        system_prompt_variant: str = "precise"
    ) -> AssembledPrompt:
        # Get base system prompt
        base_prompt = self.system_prompts.get(system_prompt_variant, self.system_prompts["precise"])
        
        # Get query type specific example
        query_type = processed_query.query_type
        type_example = self.query_type_examples.get(query_type, "")
        
        # Combine into full system prompt
        full_system_prompt = base_prompt
        if type_example:
            full_system_prompt += f"\n\n{type_example}"
        
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
