# ADR 002: Chunking Strategy

## Context
We need a chunking strategy for our documents. The options considered are:
- Fixed-size chunking
- Sentence-boundary chunking
- Semantic chunking

## Decision
We will use a hybrid approach: start with semantic chunking, and fall back to sentence-boundary + fixed-size for large documents.

## Consequences
### Positive
- **Better context preservation**: Semantic chunking groups related content together, leading to better retrieval results.
- **Flexibility**: The hybrid approach works well for all document types and sizes.
- **Controllable**: We can adjust chunk sizes based on document type.

### Negative
- **Higher complexity**: Semantic chunking requires additional processing and embedding calls.
- **Slower ingestion**: Semantic chunking will increase ingestion latency compared to fixed-size.

### Neutral
- We will use LangChain's semantic chunking implementation as a starting point.
- Default chunk size will be 512 tokens, with 100 token overlap.
