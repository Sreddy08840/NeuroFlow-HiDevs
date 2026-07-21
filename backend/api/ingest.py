import hashlib
import logging
import os
import uuid

from arq import create_pool
from arq.connections import RedisSettings
from asyncpg.pool import Pool
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.db.pool import get_db_pool
from backend.resilience.backpressure import BackpressureManager
from backend.resilience.rate_limiter import RateLimiter
from backend.security.validators import (
    validate_document_url,
    validate_file_magic_bytes,
    validate_file_type,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["ingest"])


async def get_arq_pool():
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        yield pool
    finally:
        await pool.close()


def _compute_content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _get_source_type(filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext in ["pdf"]:
        return "pdf"
    elif ext in ["docx", "doc"]:
        return "docx"
    elif ext in ["png", "jpg", "jpeg", "webp"]:
        return "image"
    elif ext in ["csv"]:
        return "csv"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")


class IngestURLRequest(BaseModel):
    url: str = Field(..., description="URL to ingest content from")


class IngestResponse(BaseModel):
    document_id: str = Field(..., description="Unique ID of the ingested document")
    status: str = Field(..., description="Current status: 'queued' or 'complete'")
    duplicate: bool = Field(..., description="Whether this document was already ingested")


@router.post(
    "/ingest",
    response_model=IngestResponse,
    tags=["Ingestion"],
    summary="Ingest a document from file or URL",
    description="Upload a file or provide a URL to ingest into NeuroFlow. Supports PDF, DOCX, images, CSV, and web URLs."
)
async def ingest(
    request: Request,
    file: UploadFile = File(None, description="File to upload and ingest"),
    url_request: IngestURLRequest = None,
    db_pool: Pool = Depends(get_db_pool),
    arq_pool = Depends(get_arq_pool)
):
    # Endpoint rate limiting: 10 req/hour/ip
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter = RateLimiter()
    allowed, wait = await rate_limiter.check_endpoint_rate_limit("ingest", client_ip, 10, 3600)
    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(int(wait))},
            content={"detail": "Too Many Requests"}
        )
    
    # Backpressure check
    backpressure = BackpressureManager()
    status, extra = await backpressure.check_backpressure()
    if status == "unavailable":
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "30"},
            content=extra
        )
    elif status == "warning":
        # Proceed but add warning to response
        pass
    if file:
        # File ingest
        file_bytes = await file.read()
        # Validate file
        validate_file_type(file)
        if file.filename:
            validate_file_magic_bytes(file_bytes, file.filename)
        content_hash = _compute_content_hash(file_bytes)
        source_type = _get_source_type(file.filename)
        
        # Check for duplicates
        async with db_pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM documents WHERE content_hash = $1",
                content_hash
            )
            if existing:
                return {"document_id": existing, "status": "complete", "duplicate": True}
            
            # Create document row
            document_id = str(uuid.uuid4())
            file_dir = os.path.join("uploads", document_id)
            os.makedirs(file_dir, exist_ok=True)
            file_path = os.path.join(file_dir, file.filename)
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            
            await conn.execute(
                """
                INSERT INTO documents (id, filename, source_type, content_hash, metadata, status)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                document_id,
                file.filename,
                source_type,
                content_hash,
                {},
                "queued"
            )
        
        # Enqueue task
        await arq_pool.enqueue_job(
            "ingest_document_task",
            document_id,
            source_type,
            file_path=file_path
        )
        
        response = {"document_id": document_id, "status": "queued", "duplicate": False}
        if status == "warning":
            response.update(extra)
        return response
    elif url_request and url_request.url:
        # URL ingest
        validated_url = validate_document_url(url_request.url)
        content_hash = hashlib.sha256(validated_url.encode()).hexdigest()
        
        async with db_pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM documents WHERE content_hash = $1",
                content_hash
            )
            if existing:
                return {"document_id": existing, "status": "complete", "duplicate": True}
            
            document_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO documents (id, filename, source_type, content_hash, metadata, status)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                document_id,
                validated_url,
                "url",
                content_hash,
                {"url": validated_url},
                "queued"
            )
        
        await arq_pool.enqueue_job(
            "ingest_document_task",
            document_id,
            "url",
            url=validated_url
        )
        
        response = {"document_id": document_id, "status": "queued", "duplicate": False}
        if status == "warning":
            response.update(extra)
        return response
    else:
        raise HTTPException(status_code=400, detail="Must provide either file or url")


@router.get(
    "/documents",
    tags=["Ingestion"],
    summary="List documents",
    description="Get a paginated list of all ingested documents, sorted by most recent first"
)
async def list_documents(
    db_pool: Pool = Depends(get_db_pool),
    limit: int = Field(50, ge=1, le=100, description="Number of documents to return per page"),
    offset: int = Field(0, ge=0, description="Number of documents to skip")
):
    async with db_pool.acquire() as conn:
        docs = await conn.fetch(
            "SELECT id, filename, source_type, status, chunk_count, metadata, created_at FROM documents ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit,
            offset
        )
        return [
            {
                "document_id": doc["id"],
                "filename": doc["filename"],
                "source_type": doc["source_type"],
                "status": doc["status"],
                "chunk_count": doc["chunk_count"],
                "metadata": doc["metadata"],
                "created_at": doc["created_at"]
            }
            for doc in docs
        ]


@router.get(
    "/documents/{document_id}",
    tags=["Ingestion"],
    summary="Get document details",
    description="Retrieve detailed information about a specific document by its ID"
)
async def get_document(
    document_id: str = Field(..., description="Unique ID of the document to retrieve"),
    db_pool: Pool = Depends(get_db_pool)
):
    async with db_pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT id, filename, source_type, status, chunk_count, metadata, created_at FROM documents WHERE id = $1",
            document_id
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return {
            "document_id": doc["id"],
            "filename": doc["filename"],
            "source_type": doc["source_type"],
            "status": doc["status"],
            "chunk_count": doc["chunk_count"],
            "metadata": doc["metadata"],
            "created_at": doc["created_at"]
        }
