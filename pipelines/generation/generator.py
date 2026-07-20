import asyncio
import time
import uuid
import json
from dataclasses import dataclass
from typing import AsyncGenerator, List, Dict, Any, Optional
import asyncpg
import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings
from opentelemetry import trace
from opentelemetry.trace import Tracer
from pipelines.retrieval import (
    Retriever, QueryProcessor, ContextAssembler, ContextWindow, ProcessedQuery
)
from pipelines.generation import PromptBuilder, CitationParser, Citation
from backend.providers import NeuroFlowClient, ChatMessage
from backend.db.pool import get_db_pool
from backend.config import settings
from backend.models import PipelineConfig
from backend.monitoring.metrics import (
    queries_total,
    retrieval_latency,
    generation_latency,
    llm_calls_total,
    llm_cost
)


tracer: Tracer = trace.get_tracer(__name__)


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

    async def _get_pipeline_config(self, pipeline_id: uuid.UUID) -> tuple[PipelineConfig, uuid.UUID]:
        """Load current pipeline config and return pipeline_version_id."""
        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT pv.id, pv.config
                FROM pipelines p
                JOIN pipeline_versions pv ON p.id = pv.pipeline_id AND p.current_version = pv.version
                WHERE p.id = $1
            """, pipeline_id)
            if not row:
                raise ValueError("Pipeline not found")
            config_dict = json.loads(row["config"])
            config = PipelineConfig(**config_dict)
            return config, row["id"]

    async def _create_pipeline_run(
        self,
        pipeline_id: uuid.UUID,
        pipeline_version_id: uuid.UUID,
        query: str,
        retrieved_chunk_ids: List[str]
    ) -> uuid.UUID:
        pool = await self._get_db_pool()
        run_id = uuid.uuid4()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pipeline_runs (
                    id, pipeline_id, pipeline_version_id, query, retrieved_chunk_ids, status
                ) VALUES ($1, $2, $3, $4, $5, 'running')
            """, run_id, pipeline_id, pipeline_version_id, query, retrieved_chunk_ids)
        return run_id

    async def _update_pipeline_run(
        self,
        run_id: uuid.UUID,
        generation: str,
        input_tokens: int,
        output_tokens: int,
        model_used: str,
        latency_ms: int,
        retrieval_latency_ms: int,
        generation_latency_ms: int,
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
                    retrieval_latency_ms = $6,
                    generation_latency_ms = $7,
                    metadata = $8,
                    status = 'complete'
                WHERE id = $9
            """, generation, input_tokens, output_tokens, model_used, latency_ms, 
                retrieval_latency_ms, generation_latency_ms, metadata or {}, run_id)

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

        # Load pipeline config
        config, pipeline_version_id = await self._get_pipeline_config(pipeline_id)

        # Step 1: Retrieval
        retrieval_start = time.time()
        yield {"type": "retrieval_start"}
        processed_query = await self.retriever.query_processor.process(query)
        retrieval_results = await self.retriever.retrieve(
            query, 
            k=config.retrieval.top_k_after_rerank,
            dense_k=config.retrieval.dense_k,
            sparse_k=config.retrieval.sparse_k,
            rrf_k=config.retrieval.rrf_k,
            rrf_dense_weight=config.retrieval.rrf_dense_weight,
            rrf_sparse_weight=config.retrieval.rrf_sparse_weight,
            rrf_metadata_weight=config.retrieval.rrf_metadata_weight,
            use_rerank=config.retrieval.reranker != "none"
        )
        retrieval_latency_ms = int((time.time() - retrieval_start) * 1000)
        
        context_assembler = ContextAssembler(max_tokens=config.generation.max_context_tokens)
        context_window = context_assembler.assemble(retrieval_results)
        retrieved_chunk_ids = [r.chunk_id for r in retrieval_results]

        # Step 2: Create pipeline run first so we can yield run_id early
        run_id = await self._create_pipeline_run(
            pipeline_id, pipeline_version_id, query, retrieved_chunk_ids
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
        generation_start = time.time()
        assembled_prompt = self.prompt_builder.build(
            query, context_window, processed_query, use_chain_of_thought,
            system_prompt_variant=config.generation.system_prompt_variant
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

        generation_latency_ms = int((time.time() - generation_start) * 1000)

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
            retrieval_latency_ms,
            generation_latency_ms,
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
        with tracer.start_as_current_span("generation.pipeline") as generation_span:
            generation_span.set_attributes({
                "pipeline_id": str(pipeline_id),
                "query": query
            })
            
            # Load pipeline config
            config, pipeline_version_id = await self._get_pipeline_config(pipeline_id)

            # Step 1: Retrieval (already instrumented, but we'll add span too)
            retrieval_start = time.time()
            processed_query = await self.retriever.query_processor.process(query)
            retrieval_results = await self.retriever.retrieve(
                query, 
                k=config.retrieval.top_k_after_rerank,
                dense_k=config.retrieval.dense_k,
                sparse_k=config.retrieval.sparse_k,
                use_rerank=config.retrieval.reranker != "none"
            )
            retrieval_latency_ms = int((time.time() - retrieval_start) * 1000)
            
            # Context assembly span
            with tracer.start_as_current_span("retrieval.assemble") as assemble_span:
                context_assembler = ContextAssembler(max_tokens=config.generation.max_context_tokens)
                context_window = context_assembler.assemble(retrieval_results)
                retrieved_chunk_ids = [r.chunk_id for r in retrieval_results]
                assemble_span.set_attributes({"chunk_count": len(retrieved_chunk_ids)})

            # Step 2: Create pipeline run
            run_id = await self._create_pipeline_run(
                pipeline_id, pipeline_version_id, query, retrieved_chunk_ids
            )
            generation_span.set_attributes({"run_id": str(run_id)})

            # Step 3: Build prompt span
            with tracer.start_as_current_span("generation.prompt_build") as prompt_span:
                assembled_prompt = self.prompt_builder.build(
                    query, context_window, processed_query, use_chain_of_thought
                )
                prompt_span.set_attributes({"prompt_tokens": len("".join([m.content for m in assembled_prompt.messages]))})

            # LLM call span and metrics
            generation_start = time.time()
            with tracer.start_as_current_span("generation.llm_call") as llm_span:
                response = await self.client.chat(assembled_prompt.messages)
                llm_span.set_attributes({
                    "model": response.model or "",
                    "input_tokens": response.input_tokens or 0,
                    "output_tokens": response.output_tokens or 0
                })
                # Update llm metrics
                llm_calls_total.labels(
                    provider=config.generation.model_provider,
                    model=response.model or config.generation.model_name,
                    task_type="chat"
                ).inc()
                # TODO: calculate cost (we'll skip for now, but placeholders)
            
            generation_latency_sec = (time.time() - generation_start)
            generation_latency.labels(model=response.model or config.generation.model_name).observe(
                generation_latency_sec
            )
            generation_latency_ms = int(generation_latency_sec * 1000)

            full_response = response.content
            thinking = ""

            # Extract thinking if present
            if use_chain_of_thought and "<think>" in full_response and "</think>" in full_response:
                start_idx = full_response.find("<think>") + len("<think>")
                end_idx = full_response.find("</think>")
                thinking = full_response[start_idx:end_idx].strip()
                full_response = full_response[:start_idx - len("<think>")] + full_response[end_idx + len("</think>"):]

            # Parse citations span
            with tracer.start_as_current_span("generation.citation_parse") as citation_span:
                citations = self.citation_parser.parse(full_response, context_window)
                citation_span.set_attributes({"citation_count": len(citations)})

            # Update pipeline run span
            with tracer.start_as_current_span("generation.log_run"):
                latency_ms = int((time.time() - start_time) * 1000)
                await self._update_pipeline_run(
                    run_id,
                    full_response,
                    response.input_tokens or 0,
                    response.output_tokens or 0,
                    response.model or "",
                    latency_ms,
                    retrieval_latency_ms,
                    generation_latency_ms,
                    metadata={"thinking": thinking} if thinking else None
                )

            # Update queries_total metric
            queries_total.labels(pipeline_id=str(pipeline_id), status="success").inc()

            # Step 6: Enqueue evaluation job asynchronously
            asyncio.create_task(self._enqueue_evaluation_job(run_id))

            return GenerationResult(
                run_id=str(run_id),
                full_response=full_response,
                citations=citations,
                thinking=thinking
            )
