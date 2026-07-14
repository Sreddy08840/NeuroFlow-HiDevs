# ADR 001: Vector Store Selection

## Context
We need a vector store for our RAG system. The options considered are:
- Pinecone (managed SaaS)
- Weaviate (open-source, self-hosted or managed)
- Qdrant (open-source, self-hosted or managed)
- PostgreSQL with pgvector (open-source, self-hosted)

## Decision
We will use PostgreSQL with pgvector as our vector store.

## Consequences
### Positive
- **Single database**: We can store both structured metadata and vectors in the same database, simplifying operations and transactions.
- **Familiar technology**: Our team already has expertise with PostgreSQL.
- **Cost-effective**: No additional managed service costs if self-hosted.
- **Strong ecosystem**: PostgreSQL has excellent tooling for backups, monitoring, and scaling.
- **Full-text search support**: We can leverage PostgreSQL's built-in full-text search for keyword search.

### Negative
- **Less specialized features**: May not have all the advanced features of dedicated vector stores (like Pinecone's hybrid search out of the box).
- **Scaling limits**: For very large datasets (100M+ vectors), dedicated vector stores might offer better performance.

### Neutral
- We will need to implement hybrid search (vector + keyword) using PostgreSQL's full-text search and pgvector together.
