import time
from collections.abc import AsyncGenerator
from typing import Optional

import redis.asyncio as redis
from config import settings
from opentelemetry import trace

from .base import ChatMessage, GenerationResult
from .router import ModelRouter, RoutingCriteria


class NeuroFlowClient:
    _instance: Optional["NeuroFlowClient"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self.redis_client = redis.from_url(settings.redis_url)
            self.router = ModelRouter(self.redis_client)
            self.tracer = trace.get_tracer(__name__)
            self._initialized = True

    async def chat(self, messages: list[ChatMessage], criteria: RoutingCriteria | None = None) -> GenerationResult:
        if criteria is None:
            criteria = RoutingCriteria(task_type="rag_generation")

        provider, model_name = await self.router.route(criteria)

        with self.tracer.start_as_current_span("neuroflow.chat") as span:
            start_time = time.time()
            result = await provider.complete(messages)
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Update span attributes
            span.set_attributes({
                "model": model_name,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
                "latency_ms": latency_ms,
            })

            # Update Redis metrics
            await self._update_metrics(model_name, result.cost_usd)

            return result

    async def chat_stream(self, messages: list[ChatMessage], criteria: RoutingCriteria | None = None) -> AsyncGenerator[str, None]:
        if criteria is None:
            criteria = RoutingCriteria(task_type="rag_generation")

        provider, model_name = await self.router.route(criteria)

        with self.tracer.start_as_current_span("neuroflow.chat_stream") as span:
            start_time = time.time()
            full_content = ""
            async for token in provider.stream(messages):
                full_content += token
                yield token
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            # Estimate tokens for span/metrics (simplified)
            estimated_input_tokens = len(str([m.content for m in messages])) // 4
            estimated_output_tokens = len(full_content) // 4
            estimated_cost = provider.cost_per_input_token * estimated_input_tokens + provider.cost_per_output_token * estimated_output_tokens

            span.set_attributes({
                "model": model_name,
                "input_tokens": estimated_input_tokens,
                "output_tokens": estimated_output_tokens,
                "cost_usd": estimated_cost,
                "latency_ms": latency_ms,
            })

            await self._update_metrics(model_name, estimated_cost)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Use OpenAI for embeddings by default
        from .openai_provider import OpenAIProvider
        provider = OpenAIProvider()

        with self.tracer.start_as_current_span("neuroflow.embed") as span:
            start_time = time.time()
            embeddings = await provider.embed(texts)
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            estimated_input_tokens = sum(len(t) for t in texts) // 4
            estimated_cost = provider.cost_per_input_token * estimated_input_tokens

            span.set_attributes({
                "model": provider.embedding_model,
                "input_tokens": estimated_input_tokens,
                "output_tokens": 0,
                "cost_usd": estimated_cost,
                "latency_ms": latency_ms,
            })

            await self._update_metrics(provider.embedding_model, estimated_cost)

            return embeddings

    async def _update_metrics(self, model_name: str, cost_usd: float) -> None:
        await self.redis_client.incr(f"metrics:model:{model_name}:calls")
        await self.redis_client.incrbyfloat(f"metrics:model:{model_name}:cost_usd", cost_usd)
