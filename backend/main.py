import uuid
from contextlib import asynccontextmanager

from api.admin import router as admin_router
from api.auth import get_current_user
from api.auth import router as auth_router
from api.compare import router as compare_router
from api.evaluations import router as evaluations_router
from api.finetune import router as finetune_router
from api.ingest import router as ingest_router
from api.pipelines import router as pipelines_router
from api.query import router as query_router
from api.runs import router as runs_router
from config import settings
from db.health import get_health_checks
from db.migrations import check_and_apply_migrations
from db.pool import close_db_pool, create_db_pool
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from resilience.backpressure import BackpressureManager
from resilience.circuit_breaker import CircuitBreaker

# Initialize OpenTelemetry
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()
otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_db_pool()
    await check_and_apply_migrations()
    yield
    # Shutdown
    await close_db_pool()


app = FastAPI(
    lifespan=lifespan,
    title="NeuroFlow API",
    description="Enterprise RAG platform API for document ingestion, querying, evaluation, and fine-tuning.",
    version="1.0.0",
    summary="NeuroFlow RAG Platform API"
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Request-ID"] = request_id
    return response


# Add OpenTelemetry middleware
app.add_middleware(OpenTelemetryMiddleware)
FastAPIInstrumentor.instrument_app(app)

# Include routers
app.include_router(auth_router)
app.include_router(ingest_router, dependencies=[get_current_user])
app.include_router(query_router, dependencies=[get_current_user])
app.include_router(runs_router, dependencies=[get_current_user])
app.include_router(pipelines_router, dependencies=[get_current_user])
app.include_router(compare_router, dependencies=[get_current_user])
app.include_router(finetune_router, dependencies=[get_current_user])
app.include_router(evaluations_router, dependencies=[get_current_user])
app.include_router(admin_router, dependencies=[get_current_user])


@app.get(
    "/health",
    summary="Get health status",
    description="Check system health: Postgres, Redis, MLflow, circuit breaker status, and queue depth"
)
async def health_check():
    postgres_check, redis_check, mlflow_check = await get_health_checks()
    
    # Circuit breaker status
    circuit_breakers = {}
    for provider in ["openai", "anthropic"]:
        cb = CircuitBreaker(provider)
        circuit_breakers[provider] = await cb.get_status()
    
    # Backpressure (queue depth)
    backpressure = BackpressureManager()
    queue_depth = await backpressure.get_queue_depth()
    
    # Determine overall status
    critical = (postgres_check["status"] == "critical" or 
                redis_check["status"] == "critical")
    degraded = (mlflow_check["status"] == "degraded" or 
                any(cb["state"] in ["open", "half-open"] 
                    for cb in circuit_breakers.values()))
    
    if critical:
        overall_status = "critical"
    elif degraded:
        overall_status = "degraded"
    else:
        overall_status = "ok"
    
    return {
        "status": overall_status,
        "checks": {
            "postgres": postgres_check,
            "redis": redis_check,
            "mlflow": mlflow_check,
            "circuit_breakers": circuit_breakers,
            "queue_depth": queue_depth,
            "worker_count": 2  # Placeholder, in real setup we'd track workers
        }
    }


@app.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Get Prometheus metrics",
    description="Prometheus metrics endpoint for monitoring system performance and health"
)
async def metrics():
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
