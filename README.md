# NeuroFlow

NeuroFlow is a production-ready Retrieval-Augmented Generation (RAG) system with built-in evaluation and fine-tuning capabilities.

## Features

- **Multi-modal Ingestion**: Supports PDF, DOCX, images, CSV, and web URLs
- **Advanced Retrieval**: Hybrid search (vector + keyword) with RRF fusion and cross-encoder reranking
- **Model Routing**: Smart LLM selection based on cost, latency, capability, and domain
- **Evaluation**: Automated LLM-as-judge evaluation with faithfulness, relevance, precision, and recall metrics
- **Fine-tuning**: Automatic fine-tuning job submission and experiment tracking with MLflow
- **API-first**: RESTful API with streaming support

## Project Structure

```
neuroflow/
├── docs/
│   ├── architecture.md    # System architecture and subsystem design
│   ├── api-contracts.md   # REST API endpoint definitions
│   └── adr/               # Architecture Decision Records
│       ├── 001-vector-store.md
│       ├── 002-chunking-strategy.md
│       ├── 003-evaluation-framework.md
│       └── 004-model-routing.md
├── .gitignore
└── README.md
```

## Getting Started

(Coming soon)

## Documentation

- [System Architecture](docs/architecture.md)
- [API Contracts](docs/api-contracts.md)
- [Architecture Decisions](docs/adr/)

## License

(Coming soon)
