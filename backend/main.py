from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from config import settings
from db.pool import create_db_pool, close_db_pool
from db.health import get_health_checks
from db.migrations import check_and_apply_migrations
from api.ingest import router as ingest_router
from api.query import router as query_router
from api.runs import router as runs_router
from api.pipelines import router as pipelines_router
from api.compare import router as compare_router
from api.finetune import router as finetune_router


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


app = FastAPI(lifespan=lifespan, title="NeuroFlow API")

# Add OpenTelemetry middleware
app.add_middleware(OpenTelemetryMiddleware)
FastAPIInstrumentor.instrument_app(app)

# Include routers
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(runs_router)
app.include_router(pipelines_router)
app.include_router(compare_router)
app.include_router(finetune_router)


@app.get("/health")
async def health_check():
    postgres_ok, redis_ok, mlflow_ok = await get_health_checks()
    return {
        "status": "ok" if all([postgres_ok, redis_ok, mlflow_ok]) else "error",
        "checks": {
            "postgres": postgres_ok,
            "redis": redis_ok,
            "mlflow": mlflow_ok
        }
    }


@app.get("/metrics", response_class=PlainTextResponse)
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
