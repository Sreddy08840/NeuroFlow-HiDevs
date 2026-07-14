# NeuroFlow API Contracts

## Authentication
All endpoints (except `/health` and `/metrics`) require authentication via Bearer token in the `Authorization` header.

## Rate Limits
- Free tier: 100 requests/hour
- Pro tier: 1000 requests/hour
- Enterprise tier: 10000 requests/hour

---

## 1. POST /ingest
Ingest a file or web URL into the vector store.

### Request
```json
{
  "source_type": "file|url",
  "file": "base64 encoded file (if source_type is file)",
  "url": "web URL (if source_type is url)",
  "metadata": {
    "title": "string",
    "author": "string",
    "tags": ["string"]
  }
}
```

### Response (202 Accepted)
```json
{
  "ingestion_id": "uuid",
  "status": "queued|processing|completed|failed",
  "message": "string"
}
```

### Error Codes
- 400 Bad Request: Invalid source type or missing required fields
- 401 Unauthorized: Missing or invalid Bearer token
- 413 Payload Too Large: File exceeds size limit (50MB)
- 429 Too Many Requests: Rate limit exceeded

---

## 2. POST /query
Execute a RAG query.

### Request
```json
{
  "query": "string",
  "pipeline_id": "uuid (optional, uses default pipeline if not provided)",
  "stream": false
}
```

### Response (200 OK)
```json
{
  "query_id": "uuid",
  "answer": "string",
  "context": [
    {
      "chunk_id": "uuid",
      "content": "string",
      "metadata": {},
      "score": 0.95
    }
  ],
  "model_used": "string",
  "latency_ms": 1234
}
```

### Error Codes
- 400 Bad Request: Missing query
- 401 Unauthorized: Missing or invalid Bearer token
- 404 Not Found: Pipeline not found
- 429 Too Many Requests: Rate limit exceeded

---

## 3. GET /query/{query_id}/stream
Server-Sent Events (SSE) stream for generation.

### Headers
- `Accept: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`

### Events
```
data: {"type": "context", "data": [...]}

data: {"type": "token", "data": "hello"}

data: {"type": "token", "data": " world"}

data: {"type": "done", "data": {"query_id": "uuid", "latency_ms": 1234}}
```

### Error Codes
- 404 Not Found: Query not found
- 401 Unauthorized: Missing or invalid Bearer token

---

## 4. GET /evaluations
Paginated evaluation results.

### Query Parameters
- `page`: integer (default 1)
- `page_size`: integer (default 20)
- `start_date`: ISO 8601 date (optional)
- `end_date`: ISO 8601 date (optional)

### Response (200 OK)
```json
{
  "page": 1,
  "page_size": 20,
  "total": 100,
  "evaluations": [
    {
      "evaluation_id": "uuid",
      "query_id": "uuid",
      "faithfulness": 0.9,
      "answer_relevance": 0.85,
      "context_precision": 0.8,
      "context_recall": 0.95,
      "user_rating": 4,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Error Codes
- 401 Unauthorized: Missing or invalid Bearer token

---

## 5. GET /evaluations/aggregate
Rolling quality metrics.

### Query Parameters
- `window_days`: integer (default 7)

### Response (200 OK)
```json
{
  "window_days": 7,
  "avg_faithfulness": 0.88,
  "avg_answer_relevance": 0.85,
  "avg_context_precision": 0.82,
  "avg_context_recall": 0.9,
  "total_evaluations": 200
}
```

### Error Codes
- 401 Unauthorized: Missing or invalid Bearer token

---

## 6. POST /pipelines
Create a named pipeline configuration.

### Request
```json
{
  "name": "string",
  "description": "string (optional)",
  "config": {
    "retrieval": {
      "top_k": 10,
      "use_rrf": true,
      "use_reranker": true
    },
    "generation": {
      "model_tier": "cheap|standard|premium",
      "temperature": 0.7
    }
  }
}
```

### Response (201 Created)
```json
{
  "pipeline_id": "uuid",
  "name": "string",
  "description": "string",
  "config": {},
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Error Codes
- 400 Bad Request: Invalid config
- 401 Unauthorized: Missing or invalid Bearer token
- 409 Conflict: Pipeline with same name already exists

---

## 7. GET /pipelines/{id}/runs
Pipeline execution history.

### Query Parameters
- `page`: integer (default 1)
- `page_size`: integer (default 20)

### Response (200 OK)
```json
{
  "page": 1,
  "page_size": 20,
  "total": 50,
  "runs": [
    {
      "run_id": "uuid",
      "query_id": "uuid",
      "status": "success|failed",
      "latency_ms": 1234,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Error Codes
- 401 Unauthorized: Missing or invalid Bearer token
- 404 Not Found: Pipeline not found

---

## 8. POST /finetune/jobs
Submit a fine-tuning job.

### Request
```json
{
  "base_model": "string",
  "min_faithfulness": 0.8,
  "min_user_rating": 4,
  "dataset_size": 1000
}
```

### Response (202 Accepted)
```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "Job submitted successfully"
}
```

### Error Codes
- 400 Bad Request: Invalid parameters
- 401 Unauthorized: Missing or invalid Bearer token
- 429 Too Many Requests: Too many concurrent jobs

---

## 9. GET /finetune/jobs/{id}
Job status and metrics.

### Response (200 OK)
```json
{
  "job_id": "uuid",
  "status": "queued|preparing|training|validating|completed|failed",
  "base_model": "string",
  "fine_tuned_model": "string (if completed)",
  "metrics": {
    "train_loss": 0.1,
    "val_loss": 0.12,
    "val_accuracy": 0.95
  },
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T01:00:00Z (if completed)"
}
```

### Error Codes
- 401 Unauthorized: Missing or invalid Bearer token
- 404 Not Found: Job not found

---

## 10. GET /health
Health check endpoint.

### Response (200 OK)
```json
{
  "status": "healthy",
  "services": {
    "database": "up",
    "vector_store": "up",
    "llm_providers": "up"
  }
}
```

---

## 11. GET /metrics
Prometheus-compatible metrics.

### Response (200 OK)
```text
# HELP neuroflow_requests_total Total number of requests
# TYPE neuroflow_requests_total counter
neuroflow_requests_total{endpoint="/query",status="200"} 100

# HELP neuroflow_latency_seconds Request latency in seconds
# TYPE neuroflow_latency_seconds histogram
neuroflow_latency_seconds_bucket{endpoint="/query",le="0.1"} 50
neuroflow_latency_seconds_bucket{endpoint="/query",le="1"} 90
neuroflow_latency_seconds_bucket{endpoint="/query",le="+Inf"} 100
```
