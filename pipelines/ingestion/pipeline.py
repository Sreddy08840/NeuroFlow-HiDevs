import hashlib
import json
import time
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import asyncpg
import redis.asyncio as redis
import arq
from arq.connections import RedisSettings
from opentelemetry import trace
from opentelemetry.trace import Tracer
from pipelines.ingestion.base import ExtractedPage
from pipelines.ingestion.chunker import create_chunks
from pipelines.ingestion.extractors.pdf_extractor import extract_pdf
from pipelines.ingestion.extractors.docx_extractor import extract_docx
from pipelines.ingestion.extractors.image_extractor import extract_image
from pipelines.ingestion.extractors.csv_extractor import extract_csv
from pipelines.ingestion.extractors.url_extractor import extract_url
from backend.providers import NeuroFlowClient
from backend.config import settings


tracer: Tracer = trace.get_tracer(__name__)


def _compute_content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


async def _create_db_connection():
    return await asyncpg.connect(settings.database_url)


async def ingest_document_task(
    ctx,
    document_id: str,
    source_type: str,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
):
    start_time = time.time()
    conn = await _create_db_connection()
    
    with tracer.start_as_current_span("ingestion.process") as span:
        try:
            # Update status to processing
            await conn.execute(
                "UPDATE documents SET status = $1 WHERE id = $2",
                "processing",
                document_id
            )
            
            # Extract content
            file_bytes = None
            if source_type in ["pdf", "docx", "image", "csv"] and file_path:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
            
            # Get extractor
            pages: List[ExtractedPage] = []
            if source_type == "pdf":
                pages = extract_pdf(file_bytes)
            elif source_type == "docx":
                pages = extract_docx(file_bytes)
            elif source_type == "image":
                pages = await extract_image(file_bytes)
            elif source_type == "csv":
                pages = extract_csv(file_bytes)
            elif source_type == "url" and url:
                pages = await extract_url(url)
            
            # Chunk
            chunks = create_chunks(pages, source_type, num_pages=len(pages))
            
            # Embed
            client = NeuroFlowClient()
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await client.embed(chunk_texts)
            
            # Insert chunks
            chunk_count = len(chunks)
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await conn.execute(
                    """
                    INSERT INTO chunks (document_id, content, embedding, chunk_index, token_count, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    document_id,
                    chunk.content,
                    embedding,
                    chunk.chunk_index,
                    chunk.token_count,
                    json.dumps(chunk.metadata)
                )
            
            # Update document
            total_tokens = sum(c.token_count for c in chunks)
            await conn.execute(
                """
                UPDATE documents
                SET status = $1, chunk_count = $2
                WHERE id = $3
                """,
                "complete",
                chunk_count,
                document_id
            )
            
            # Log
            duration_ms = (time.time() - start_time) * 1000
            print(json.dumps({
                "event": "ingestion_complete",
                "document_id": document_id,
                "duration_ms": duration_ms,
                "chunks": chunk_count,
                "tokens": total_tokens
            }))
            
            span.set_attributes({
                "document_id": document_id,
                "source_type": source_type,
                "page_count": len(pages),
                "chunk_count": chunk_count,
                "embedding_calls": 1
            })
            
        except Exception as e:
            await conn.execute(
                "UPDATE documents SET status = $1 WHERE id = $2",
                "failed",
                document_id
            )
            raise e
        finally:
            await conn.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [ingest_document_task]


# Main worker entry point
if __name__ == "__main__":
    arq.run_worker(WorkerSettings)
