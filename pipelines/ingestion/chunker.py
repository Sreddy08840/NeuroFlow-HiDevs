import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import tiktoken
from pipelines.ingestion.base import ExtractedPage
from backend.providers import OpenAIProvider


@dataclass
class Chunk:
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    token_count: int


def _sentence_splitter(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences


def _count_tokens(text: str, tokenizer: tiktoken.Encoding) -> int:
    return len(tokenizer.encode(text, disallowed_special=()))


def _fixed_size_chunks(
    text: str,
    tokenizer: tiktoken.Encoding,
    chunk_size: int = 512,
    overlap: int = 64
) -> List[str]:
    sentences = _sentence_splitter(text)
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_tokens = _count_tokens(sentence, tokenizer)
        # Check if adding sentence exceeds chunk size
        if current_length + sentence_tokens > chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap sentences
                overlap_tokens = 0
                overlap_chunk = []
                for sent in reversed(current_chunk):
                    sent_tok = _count_tokens(sent, tokenizer)
                    if overlap_tokens + sent_tok <= overlap:
                        overlap_chunk.insert(0, sent)
                        overlap_tokens += sent_tok
                    else:
                        break
                current_chunk = overlap_chunk
                current_length = overlap_tokens
        current_chunk.append(sentence)
        current_length += sentence_tokens
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


async def _semantic_chunks(
    text: str,
    tokenizer: tiktoken.Encoding,
    similarity_threshold: float = 0.7
) -> List[str]:
    sentences = _sentence_splitter(text)
    if len(sentences) <= 1:
        return [text]
    
    provider = OpenAIProvider()
    # Embed each sentence
    embeddings = await provider.embed(sentences)
    
    # Compute cosine similarities
    chunks = []
    current_chunk = [sentences[0]]
    
    for i in range(1, len(sentences)):
        # Compute cosine similarity between current sentence and previous
        # Cosine similarity of normalized vectors is dot product
        # We assume embeddings are normalized (OpenAI's are)
        sim = sum(a * b for a, b in zip(embeddings[i-1], embeddings[i]))
        
        if sim < similarity_threshold:
            # Split here
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
        else:
            current_chunk.append(sentences[i])
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


def _hierarchical_chunks(
    pages: List[ExtractedPage],
    tokenizer: tiktoken.Encoding
) -> List[Tuple[str, Dict[str, Any]]]:
    # For simplicity, group by heading_level if available
    chunks = []
    current_parent = None
    current_parent_idx = -1
    
    for page in pages:
        if page.metadata.get("heading_level"):
            # New parent
            chunks.append((page.content, {"is_parent": True, "heading_level": page.metadata["heading_level"], "children": []}))
            current_parent_idx = len(chunks) - 1
        else:
            if current_parent_idx >= 0:
                chunks[-1][1]["children"].append(page.content)
            chunks.append((page.content, {"is_parent": False, "parent_idx": current_parent_idx if current_parent_idx >=0 else None}))
    
    return chunks


def create_chunks(
    pages: List[ExtractedPage],
    source_type: str,
    num_pages: int = None,
    chunk_size: int = 512,
    chunk_overlap: int = 64
) -> List[Chunk]:
    # Select strategy
    tokenizer = tiktoken.get_encoding("cl100k_base")
    all_chunks = []
    
    if any(p.content_type == "table" for p in pages):
        # Table content: fixed size
        strategy = "fixed_size"
    elif source_type == "docx" and any(p.metadata.get("heading_level") for p in pages):
        strategy = "hierarchical"
    elif source_type == "pdf" and num_pages and num_pages > 50:
        strategy = "semantic"
    else:
        strategy = "fixed_size"
    
    chunk_index = 0
    for page in pages:
        if page.content_type == "table":
            # Tables always get fixed size
            table_chunks = _fixed_size_chunks(page.content, tokenizer, chunk_size, chunk_overlap)
            for chunk_text in table_chunks:
                all_chunks.append(Chunk(
                    content=chunk_text,
                    chunk_index=chunk_index,
                    metadata={
                        "page_number": page.page_number,
                        "content_type": "table",
                        "strategy": "fixed_size",
                        **page.metadata
                    },
                    token_count=_count_tokens(chunk_text, tokenizer)
                ))
                chunk_index += 1
        else:
            if strategy == "hierarchical":
                # We'll handle hierarchical as fixed size for now, keep metadata
                page_chunks = _fixed_size_chunks(page.content, tokenizer, chunk_size, chunk_overlap)
                for chunk_text in page_chunks:
                    all_chunks.append(Chunk(
                        content=chunk_text,
                        chunk_index=chunk_index,
                        metadata={
                            "page_number": page.page_number,
                            "content_type": "text",
                            "strategy": "hierarchical",
                            **page.metadata
                        },
                        token_count=_count_tokens(chunk_text, tokenizer)
                    ))
                    chunk_index += 1
            else:
                # Fixed or semantic
                if strategy == "fixed_size":
                    page_chunks = _fixed_size_chunks(page.content, tokenizer, chunk_size, chunk_overlap)
                else:  # semantic
                    # Semantic is async, but we'll run in pipeline
                    # For now, use fixed size as fallback
                    page_chunks = _fixed_size_chunks(page.content, tokenizer, chunk_size, chunk_overlap)
                
                for chunk_text in page_chunks:
                    all_chunks.append(Chunk(
                        content=chunk_text,
                        chunk_index=chunk_index,
                        metadata={
                            "page_number": page.page_number,
                            "content_type": "text",
                            "strategy": strategy,
                            **page.metadata
                        },
                        token_count=_count_tokens(chunk_text, tokenizer)
                    ))
                    chunk_index += 1
    
    return all_chunks
