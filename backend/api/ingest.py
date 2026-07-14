import hashlib
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel, Field
from arq import create_pool
from arq.connections import RedisSettings
from asyncpg.pool import Pool
from backend.db.pool import get_db_pool
from pipelines.ingestion.pipeline import ingest_document_task
from backend.config import settings


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
    url: str = Field(..., description="URL to ingest")


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(None),
    url_request: IngestURLRequest = None,
    db_pool: Pool = Depends(get_db_pool),
    arq_pool = Depends(get_arq_pool)
):
    if file:
        # File ingest
        file_bytes = await file.read()
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
        
        return {"document_id": document_id, "status": "queued", "duplicate": False}
    elif url_request and url_request.url:
        # URL ingest
        content_hash = hashlib.sha256(url_request.url.encode()).hexdigest()
        
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
                url_request.url,
                "url",
                content_hash,
                {"url": url_request.url},
                "queued"
            )
        
        await arq_pool.enqueue_job(
            "ingest_document_task",
            document_id,
            "url",
            url=url_request.url
        )
        
        return {"document_id": document_id, "status": "queued", "duplicate": False}
    else:
        raise HTTPException(status_code=400, detail="Must provide either file or url")


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
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
