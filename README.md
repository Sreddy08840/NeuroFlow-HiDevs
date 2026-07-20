# NeuroFlow

NeuroFlow is a production-ready Retrieval-Augmented Generation (RAG) system with built-in evaluation and fine-tuning capabilities.

## Features

- **Multi-modal Ingestion**: Supports PDF, DOCX, images, CSV, and web URLs
- **Advanced Retrieval**: Hybrid search (vector + keyword) with RRF fusion and cross-encoder reranking
- **Model Routing**: Smart LLM selection based on cost, latency, capability, and domain
- **Evaluation**: Automated LLM-as-judge evaluation with faithfulness, relevance, precision, and recall metrics
- **Fine-tuning**: Automatic fine-tuning job submission and experiment tracking with MLflow
- **API-first**: RESTful API with streaming support

## Live Demo

- **API Health Check**: https://neuroflow-api.railway.app/health
- **Deployment Guide**: [docs/deployment.md](docs/deployment.md)

## Project Structure

```
neuroflow/
├── docs/
│   ├── architecture.md    # System architecture and subsystem design
│   ├── api-contracts.md   # REST API endpoint definitions
│   ├── deployment.md      # Cloud deployment guide (Railway)
│   └── adr/               # Architecture Decision Records
├── backend/               # FastAPI application
├── frontend/              # Next.js web app
├── pipelines/             # RAG pipeline components
├── infra/                 # Docker, Nginx, Prometheus configs
└── tests/                 # Unit, integration, and performance tests
```

## Getting Started

### Local Development

```bash
# Copy env file
cp .env.example .env
# Edit .env with your secrets

# Start services
docker-compose up --build
```

### Cloud Deployment

See [deployment guide](docs/deployment.md) for detailed Railway deployment steps.

## Documentation

- [System Architecture](docs/architecture.md)
- [API Contracts](docs/api-contracts.md)
- [Deployment Guide](docs/deployment.md)
- [Architecture Decisions](docs/adr/)

## License

(Coming soon)
