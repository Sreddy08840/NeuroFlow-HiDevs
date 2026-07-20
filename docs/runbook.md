# NeuroFlow Operations Runbook

## Incident 1 — High Query Latency (P95 > 10s)

### Checks
1. **Check Jaeger traces**: Look for slow spans (retrieval, generation, embedding)
2. **Check Redis metrics**:
   - Memory usage
   - Cache hit rate (`redis-cli info stats | grep keyspace_hits`)
3. **Check Postgres performance**:
   - Use `pg_stat_statements` for slow queries
   - Verify vector index usage
4. **Check API pod metrics**: CPU/memory usage, number of replicas

### Remediation Steps
1. Flush Redis cache: `redis-cli FLUSHDB`
2. Add indexes to `chunks` or `pipeline_runs` tables if missing
3. Scale API deployment replicas: `kubectl scale deployment api --replicas=5`
4. Increase HNSW ef_search parameter temporarily for better recall/latency tradeoff


## Incident 2 — Evaluation Scores Degrading

### Checks
1. **Check which pipeline/metric**: Look at Prometheus metrics or MLflow
2. **Check recent ingestions**: Did we ingest low‑quality/spam documents?
3. **Check MLflow**: Any recent fine‑tuning jobs that might have regressed performance?
4. **Check prompt changes**: Did we modify system prompts or query expansion?

### Remediation Steps
1. Revert last fine‑tuned model
2. Remove or archive low‑quality documents
3. Roll back prompt changes to last known good version
4. Run retrieval benchmark suite to confirm improvement


## Incident 3 — LLM Provider Circuit Breaker Open

### Checks
1. **Check health endpoint**: `GET /health` — look for `circuit_breaker_open: true`
2. **Check provider status page**: e.g., OpenAI status, Anthropic status
3. **Check logs**: Look for recent provider errors (timeouts, 429s, 500s)

### Remediation Steps
1. Wait for recovery timeout (default: 60s)
2. Manually reset circuit breaker: `POST /admin/circuit-breaker/reset`
3. Consider switching to backup provider if primary is down


## Incident 4 — Ingestion Queue Depth > 100

### Checks
1. **Check health endpoint**: `GET /health` — look for `queue_depth` metric
2. **Check worker logs**: Any errors processing jobs?
3. **Check Redis**: Inspect queue contents: `redis-cli LRANGE arq:queue 0 -1`

### Remediation Steps
1. Restart worker containers: `kubectl rollout restart deployment worker`
2. Clear stuck jobs in Redis if needed
3. Scale worker replicas: `kubectl scale deployment worker --replicas=3`


## Incident 5 — Database Disk Usage > 80%

### Checks
1. **Check table sizes**:
   ```sql
   SELECT
       relname AS table_name,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
   FROM pg_stat_user_tables
   ORDER BY pg_total_relation_size(relid) DESC;
   ```
2. **Check data retention job logs**: Is it running daily?
3. **Check archived documents**: Are chunks still present for archived docs?

### Remediation Steps
1. Run data retention job manually: `POST /admin/retention/run`
2. Archive old unused documents
3. Increase database disk size or set up automatic volume expansion
