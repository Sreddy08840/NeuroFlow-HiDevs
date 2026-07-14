# NeuroFlow System Architecture

## 1. Ingestion Subsystem

Accepts raw files (PDF, DOCX, images, CSV, web URLs), extracts content per modality, chunks, embeds, and writes to the vector store.

### Data Flow Diagram
```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ User Input  │────▶│ Modality     │────▶│ Content      │────▶│ Chunking     │────▶│ Embedding    │────▶│ Vector Store │
│ (File/URL)  │     │ Router       │     │ Extraction   │     │ Engine       │     │ Model        │     │ (pgvector)   │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Components
- **Modality Router**: Determines file type and routes to appropriate extractor
- **Content Extractors**: 
  - PDF: PyMuPDF / PyPDF2 for text, GPT-4V / CLIP for images
  - DOCX: python-docx
  - Images: OCR (Tesseract) + vision models
  - CSV: pandas
  - Web URLs: requests + BeautifulSoup
- **Chunking Engine**: Handles semantic and fixed-size chunking
- **Embedding Model**: OpenAI text-embedding-3-small / sentence-transformers
- **Vector Store**: PostgreSQL with pgvector extension

---

## 2. Retrieval Subsystem

Given a user query, runs embedding similarity search, keyword search, and metadata filtering in parallel, fuses results via Reciprocal Rank Fusion, passes through a cross-encoder reranker, and returns a ranked context window.

### Full Retrieval Pipeline Diagram
```
                     ┌──────────────────────────────┐
                     │        User Query            │
                     └──────────────┬───────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Embedding Similarity │  │ Keyword Search       │  │ Metadata Filtering   │
│   (Vector Search)    │  │   (BM25/TF-IDF)      │  │   (SQL Filters)      │
└───────────┬──────────┘  └───────────┬──────────┘  └───────────┬──────────┘
            │                          │                          │
            └──────────────────────┬───┴──────────────────────────┘
                                   │
                                   ▼
                     ┌──────────────────────────────┐
                     │ Reciprocal Rank Fusion (RRF) │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │ Cross-Encoder Reranker       │
                     │   (e.g., BAAI/bge-reranker)  │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │ Ranked Context Window        │
                     └──────────────────────────────┘
```

### Components
- **Embedding Similarity Search**: cosine similarity on pgvector
- **Keyword Search**: PostgreSQL full-text search / BM25
- **Metadata Filtering**: SQL WHERE clauses on document metadata
- **Reciprocal Rank Fusion**: Combines results from multiple search methods
- **Cross-Encoder Reranker**: Re-ranks top-k candidates for better precision

---

## 3. Generation Subsystem

Assembles the context window into a prompt, routes to the appropriate LLM (by cost tier, capability, or domain), streams the response token by token, and logs the complete input/output pair for evaluation.

### Components
- **Prompt Assembly**: Constructs RAG prompt with context, question, and instructions
- **Model Router**: Routes query to appropriate LLM based on:
  - Cost tier (cheap → expensive)
  - Capability (simple → complex queries)
  - Domain expertise
- **LLM Providers**: OpenAI GPT-4o, GPT-3.5-turbo, Anthropic Claude, etc.
- **Streaming**: Server-Sent Events (SSE) for token-by-token delivery
- **Query Logging**: Stores complete input/output for evaluation and fine-tuning

---

## 4. Evaluation Subsystem

Asynchronously scores every generation on:
- Faithfulness (are claims grounded in retrieved context?)
- Answer relevance (does it address the question?)
- Context precision (are retrieved chunks actually used?)
- Context recall (were relevant chunks retrieved?)

Stores scores in Postgres and computes rolling aggregates.

### Components
- **Async Evaluation Worker**: Celery / RQ task queue
- **LLM-as-Judge**: Evaluates generations using another LLM
- **Metrics Database**: PostgreSQL tables for evaluation scores
- **Aggregation Engine**: Computes rolling averages, percentiles, etc.

---

## 5. Fine-Tuning Subsystem

Extracts high-quality prompt/completion pairs from the evaluation log (where faithfulness > 0.8 AND user rating >= 4), formats them as JSONL training data, submits fine-tuning jobs, tracks experiments in MLflow, and routes future similar queries to the fine-tuned model when it outperforms the base model.

### Components
- **Training Data Extractor**: Filters evaluation logs for high-quality pairs
- **JSONL Formatter**: Prepares training data for LLM fine-tuning
- **Fine-Tuning Job Manager**: Submits jobs to OpenAI/Anthropic APIs
- **MLflow Tracker**: Tracks experiment metrics and artifacts
- **Model Router Update**: Switches to fine-tuned model when it performs better
