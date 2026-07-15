import re
import tiktoken
from dataclasses import dataclass
from typing import List, Any
from .base import RetrievalResult


@dataclass
class ContextWindow:
    content: str
    chunks_used: List[RetrievalResult]
    total_tokens: int
    sources: List[dict[str, Any]]


class ContextAssembler:
    def __init__(
        self,
        tokenizer_name: str = "cl100k_base",
        max_tokens: int = 4000
    ):
        self.tokenizer = tiktoken.get_encoding(tokenizer_name)
        self.max_tokens = max_tokens

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def assemble(
        self,
        results: List[RetrievalResult],
        max_tokens: int | None = None
    ) -> ContextWindow:
        max_tokens = max_tokens or self.max_tokens
        used_chunks = []
        sources = []
        content_parts = []
        total_tokens = 0

        for result in results:
            # Build chunk content with source header
            doc_name = result.metadata.get("filename", result.document_id)
            page = result.metadata.get("page_number", "N/A")
            source_header = f"[Source {len(sources)+1} — {doc_name}, page {page}]"
            chunk_content = f"{source_header}\n{result.content}\n\n"
            chunk_tokens = self._count_tokens(chunk_content)

            if total_tokens + chunk_tokens <= max_tokens:
                content_parts.append(chunk_content)
                used_chunks.append(result)
                sources.append({
                    "chunk_id": result.chunk_id,
                    "document_id": result.document_id,
                    "metadata": result.metadata
                })
                total_tokens += chunk_tokens
            else:
                break

        return ContextWindow(
            content="".join(content_parts),
            chunks_used=used_chunks,
            total_tokens=total_tokens,
            sources=sources
        )
