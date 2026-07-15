import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator, List, Dict, Any, Optional
import asyncpg
import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings
from pipelines.retrieval import (
    Retriever, QueryProcessor, ContextAssembler, ContextWindow, ProcessedQuery
)
from pipelines.generation import PromptBuilder, CitationParser, Citation
from backend.providers import NeuroFlowClient, ChatMessage
from backend.db.pool import get_db_pool
from backend.config import settings


@dataclass
class GenerationResult:
    run_id: str
    full_response: str
    citations: List[Citation]
    thinking: Optional[str] = None


class Generator:
    def __init__(
        self,
        db_pool: Optional[asyncpg.Pool] = None,
        redis_client: Optional[redis.Redis] = None,
        retriever: Optional[Retriever] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        citation_parser: Optional[CitationParser] = None,
        client: Optional[NeuroFlowClient] = None
    ):
        self.db_pool = db_pool
        self.redis_client = redis_client
        self.retriever = retriever or Retriever()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.citation_parser = citation_parser or CitationParser()
        self.client = client or NeuroFlowClient()

    async def _get_db_pool(self):
        if self.db_pool is None:
            self.db_pool = await get_db_pool()
        return self.db_pool

    async def _get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = redis.from_url(settings.redis_url)
        return self.redis_client

    async def _create_pipeline_run(
        self,
        pipeline_id: uuid.UUID,
        query: str,
        retrieved_chunk_ids: List[str]
    ) -> uuid.UUID:
        pool = await self._get_db_pool()
        run_id = uuid.uuid4()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pipeline_runs (
                    id, pipeline_id, query, retrieved_chunk_ids, status
                ) VALUES ($1, $2, $3, $4, 'running')
            """, run_id, pipeline_id, query, retrieved_chunk_ids)
        return run_id

    async def _update_pipeline_run(
        self,
        run_id: uuid.UUID,
        generation: str,
        input_tokens: int,
        output_tokens: int,
        model_used: str,
        latency_ms: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE pipeline_runs
                SET generation = $1,
                    input_tokens = $2,
                    output_tokens = $3,
                    model_used = $4,
                    latency_ms = $5,
                    metadata = $6,
                    status = 'complete'
                WHERE id = $7
            """, generation, input_tokens, output_tokens, model_used, latency_ms, metadata or {}, run_id)

    async def _enqueue_evaluation_job(self, run_id: uuid.UUID):
        try:
            # Enqueue job using arq
            redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis_pool.enqueue_job("process_evaluation_job", str(run_id))
            await redis_pool.close()
        except Exception:
            # Don't fail the whole request if evaluation enqueue fails
            pass

    async def generate_stream(
        self,
        query: str,
        pipeline_id: uuid.UUID,
        use_chain_of_thought: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        start_time = time.time()

        # Step 1: Retrieval
        yield {"type": "retrieval_start"}
        processed_query = await self.retriever.query_processor.process(query)
        retrieval_results = await self.retriever.retrieve(query, k=20)
        context_assembler = ContextAssembler()
        context_window = context_assembler.assemble(retrieval_results)
        retrieved_chunk_ids = [r.chunk_id for r in retrieval_results]

        # Step 2: Create pipeline run first so we can yield run_id early
        run_id = await self._create_pipeline_run(
            pipeline_id, query, retrieved_chunk_ids
        )
        yield {"type": "run_id", "run_id": str(run_id)}

        yield {
            "type": "retrieval_complete",
            "chunk_count": len(retrieval_results),
            "sources": [
                {"document": s.get("metadata", {}).get("filename", s.get("document_id")), "page": s.get("metadata", {}).get("page_number")}
                for s in context_window.sources
            ]
        }

        # Step 3: Build prompt and generate
        assembled_prompt = self.prompt_builder.build(
            query, context_window, processed_query, use_chain_of_thought
        )

        full_response = ""
        thinking = ""
        in_thinking = False
        input_tokens = 0
        output_tokens = 0
        model_used = ""

        # Stream tokens
        async for delta in self.client.chat_stream(assembled_prompt.messages):
            # Handle chain-of-thought
            if use_chain_of_thought and "<think>" in delta:
                in_thinking = True
            if use_chain_of_thought and "</think>" in delta:
                in_thinking = False

            if in_thinking:
                thinking += delta
            else:
                # Strip think tags from streamed content
                clean_delta = delta
                clean_delta = clean_delta.replace("<think>", "").replace("</think>", "")
                if clean_delta:
                    yield {"type": "token", "delta": clean_delta}
                    full_response += clean_delta

        # Step 4: Parse citations
        citations = self.citation_parser.parse(full_response, context_window)

        # Step 5: Update pipeline run
        latency_ms = int((time.time() - start_time) * 1000)
        await self._update_pipeline_run(
            run_id,
            full_response,
            input_tokens,
            output_tokens,
            model_used,
            latency_ms,
            metadata={"thinking": thinking} if thinking else None
        )

        # Step 6: Enqueue evaluation job asynchronously
        asyncio.create_task(self._enqueue_evaluation_job(run_id))

        # Step 7: Send done event
        yield {
            "type": "done",
            "run_id": str(run_id),
            "citations": [
                {
                    "source": c.reference,
                    "chunk_id": c.chunk_id,
                    "document": c.document_name,
                    "page": c.page_number,
                    "invalid_citation": c.invalid_citation
                }
                for c in citations
            ]
        }

    async def generate(
        self,
        query: str,
        pipeline_id: uuid.UUID,
        use_chain_of_thought: bool = True
    ) -> GenerationResult:
        start_time = time.time()

        # Step 1: Retrieval
        processed_query = await self.retriever.query_processor.process(query)
        retrieval_results = await self.retriever.retrieve(query, k=20)
        context_assembler = ContextAssembler()
        context_window = context_assembler.assemble(retrieval_results)
        retrieved_chunk_ids = [r.chunk_id for r in retrieval_results]

        # Step 2: Create pipeline run
        run_id = await self._create_pipeline_run(
            pipeline_id, query, retrieved_chunk_ids
        )

        # Step 3: Build prompt and generate
        assembled_prompt = self.prompt_builder.build(
            query, context_window, processed_query, use_chain_of_thought
        )
        response = await self.client.chat(assembled_prompt.messages)

        full_response = response.content
        thinking = ""

        # Extract thinking if present
        if use_chain_of_thought and "<think>" in full_response and "</think>" in full_response:
            start_idx = full_response.find("<think>") + len("<think>")
            end_idx = full_response.find("</think>")
            thinking = full_response[start_idx:end_idx].strip()
            full_response = full_response[:start_idx - len("<think>")] + full_response[end_idx + len("</think>"):]

        # Step 4: Parse citations
        citations = self.citation_parser.parse(full_response, context_window)

        # Step 5: Update pipeline run
        latency_ms = int((time.time() - start_time) * 1000)
        await self._update_pipeline_run(
            run_id,
            full_response,
            response.input_tokens or 0,
            response.output_tokens or 0,
            response.model or "",
            latency_ms,
            metadata={"thinking": thinking} if thinking else None
        )

        # Step 6: Enqueue evaluation job asynchronously
        asyncio.create_task(self._enqueue_evaluation_job(run_id))

        return GenerationResult(
            run_id=str(run_id),
            full_response=full_response,
            citations=citations,
            thinking=thinking
        )
