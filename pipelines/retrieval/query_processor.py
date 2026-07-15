import json
from typing import Any
from .base import ProcessedQuery
from backend.providers import NeuroFlowClient, ChatMessage


class QueryProcessor:
    def __init__(self, client: NeuroFlowClient | None = None):
        self.client = client or NeuroFlowClient()

    async def process(self, query: str) -> ProcessedQuery:
        # Run all three processing steps in parallel
        expanded, filter_dict, query_type = await self._run_all_steps(query)
        return ProcessedQuery(
            original=query,
            expanded=expanded,
            metadata_filter=filter_dict,
            query_type=query_type
        )

    async def _run_all_steps(self, query: str):
        import asyncio
        return await asyncio.gather(
            self._expand_query(query),
            self._extract_metadata_filter(query),
            self._classify_query_type(query)
        )

    async def _expand_query(self, query: str) -> list[str]:
        messages = [
            ChatMessage(role="system", content="You generate 2-3 alternative phrasings of the user's query. No additional text, just the phrasings, one per line, numbered."),
            ChatMessage(role="user", content=f"Query: {query}")
        ]
        result = await self.client.chat(messages)
        # Parse response into list
        lines = result.content.splitlines()
        expanded = []
        for line in lines:
            line = line.strip()
            if line:
                # Remove numbering if present
                if line[0].isdigit():
                    line = line.split(".", 1)[1].strip()
                expanded.append(line)
        return expanded[:3]

    async def _extract_metadata_filter(self, query: str) -> dict[str, Any]:
        messages = [
            ChatMessage(role="system", content="You extract metadata filters from queries. Return only valid JSON with keys as filter names, no extra text."),
            ChatMessage(role="user", content=f"Query: {query}\nExample: query '2023 climate documents' → {{'year': 2023, 'topic': 'climate'}}")
        ]
        result = await self.client.chat(messages)
        try:
            content = result.content.strip()
            # Try to extract JSON
            if content.startswith("```json"):
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    async def _classify_query_type(self, query: str) -> str:
        messages = [
            ChatMessage(role="system", content="Classify this query as one of: factual, analytical, comparative, procedural. Return only the single word."),
            ChatMessage(role="user", content=f"Query: {query}")
        ]
        result = await self.client.chat(messages)
        q_type = result.content.strip().lower()
        valid_types = ["factual", "analytical", "comparative", "procedural"]
        if q_type in valid_types:
            return q_type
        return "factual"
