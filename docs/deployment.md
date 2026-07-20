# NeuroFlow Deployment Guide

## Prerequisites

- [Railway CLI](https://docs.railway.app/guides/cli) installed (`npm install -g @railway/cli`)
- A GitHub account connected to Railway
- OpenAI API key

## Deployment Steps

### 1. Initialize Railway Project

```bash
# Login to Railway
railway login

# Initialize project in current directory
railway init
```

### 2. Provision Database (PostgreSQL with pgvector)

Add a PostgreSQL service from the Railway Dashboard or CLI:

```bash
railway add postgres
```

Railway will automatically set:
- `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`
- `DATABASE_URL` (we'll use this for our app)

**Enable pgvector:**
After database is provisioned, connect via psql and install the extension:
```sql
CREATE EXTENSION vector;
```

### 3. Provision Redis

```bash
railway add redis
```

Railway will automatically set:
- `REDIS_URL`
- `REDISHOST`, `REDISPORT`, `REDISUSER`, `REDISPASSWORD`

### 4. Configure Environment Variables

In Railway Dashboard → Variables:

```
# Required
OPENAI_API_KEY=your_openai_api_key
JWT_SECRET_KEY=generated_256bit_key  # openssl rand -hex 32
PLUGIN_SECRETS_KEY=generated_fernet_key  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENVIRONMENT=production
LOG_LEVEL=INFO
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
MLFLOW_TRACKING_URI=${{Postgres.DATABASE_URL}}

# Optional
ANTHROPIC_API_KEY=your_anthropic_api_key
SENTRY_DSN=your_sentry_dsn
OTEL_EXPORTER_OTLP_ENDPOINT=your_otel_endpoint
```

### 5. Deploy Services

Create a `railway.json` file in project root to define services:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  },
  "services": [
    {
      "name": "api",
      "build": {
        "dockerfilePath": "backend/Dockerfile"
      },
      "deploy": {
        "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT"
      }
    },
    {
      "name": "worker",
      "build": {
        "dockerfilePath": "backend/Dockerfile"
      },
      "deploy": {
        "startCommand": "python worker.py"
      }
    }
  ]
}
```

Deploy:
```bash
railway up
```

### 6. Run Database Migrations

Connect to Railway Postgres and run the initialization scripts from `infra/init/`:
- `001_schema.sql`
- `002_rls.sql`

## Production Verification Checklist

| Step | Check | Result |
|------|-------|--------|
| 1 | GET `/health` → all checks green | ✅ |
| 2 | Upload `tests/fixtures/test_doc.pdf` via POST `/ingest` → status reaches `complete` | ✅ |
| 3 | Submit query about test document → generation completes with citations | ✅ |
| 4 | GET `/evaluations` → entry with scores exists | ✅ |
| 5 | GET `/query/{run_id}/stream` → tokens arrive progressively | ✅ |
| 6 | MLflow experiments visible | ✅ |
| 7 | GET `/metrics` → custom metrics present | ✅ |
| 8 | Load test (10 users, 2 min) succeeds | ✅ |

## Rollback Procedure

### 1. Redeploy Previous Docker Image Tag

```bash
# List available deployments
railway deployments list

# Rollback to specific deployment
railway rollback <deployment-id>
```

### 2. Reverse Database Migrations (if applicable)

Since we use idempotent migrations, re-run the last working schema version.

### 3. Verify Rollback Succeeded

Check:
- GET `/health` → green
- Application version matches previous tag
- Core functionality works

## Preview Deployments (Optional)

Configure GitHub Actions to deploy preview environments for every PR using isolated schema prefixes in the same staging database.

Example workflow:
- Trigger on PR opened/updated
- Deploy to Railway with unique service name
- Cleanup on PR closed

