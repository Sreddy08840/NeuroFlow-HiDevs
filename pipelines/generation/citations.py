import re
from dataclasses import dataclass
from typing import List, Dict, Any, Set
from pipelines.retrieval import ContextWindow


@dataclass
class Citation:
    reference: str        # "Source 1"
    chunk_id: str
    document_name: str
    page_number: int | None
    content_preview: str  # first 100 chars of cited chunk
    invalid_citation: bool = False


class CitationParser:
    def __init__(self):
        self.citation_pattern = re.compile(r'\[Source (\d+)\]')

    def parse(
        self,
        response_text: str,
        context_window: ContextWindow
    ) -> List[Citation]:
        citations: List[Citation] = []
        seen_references: Set[str] = set()

        # Find all [Source N] references
        matches = self.citation_pattern.findall(response_text)
        for match in matches:
            source_num = int(match)
            reference = f"Source {source_num}"

            if reference in seen_references:
                continue
            seen_references.add(reference)

            # Check if source number is valid
            if source_num < 1 or source_num > len(context_window.sources):
                citations.append(Citation(
                    reference=reference,
                    chunk_id="",
                    document_name="",
                    page_number=None,
                    content_preview="",
                    invalid_citation=True
                ))
                continue

            # Get source info
            source_idx = source_num - 1
            source = context_window.sources[source_idx]
            chunk = context_window.chunks_used[source_idx]

            document_name = chunk.metadata.get("filename", chunk.document_id)
            page_number = chunk.metadata.get("page_number")
            content_preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content

            citations.append(Citation(
                reference=reference,
                chunk_id=chunk.chunk_id,
                document_name=document_name,
                page_number=page_number,
                content_preview=content_preview,
                invalid_citation=False
            ))

        return citations
