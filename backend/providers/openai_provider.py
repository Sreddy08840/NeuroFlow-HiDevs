import asyncio
import time
from typing import AsyncGenerator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from openai import RateLimitError
from .base import BaseLLMProvider, ChatMessage, GenerationResult
from config import settings


class OpenAIProvider(BaseLLMProvider):
    PRICE_TABLE = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    }

    CONTEXT_WINDOWS = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
    }

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini", embedding_model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        self.model = model
        self.embedding_model = embedding_model
        self.max_retries = 3
        self.initial_backoff = 1  # seconds

    async def _retry_with_exponential_backoff(self, func, *args, **kwargs):
        retries = 0
        while retries < self.max_retries:
            try:
                return await func(*args, **kwargs)
            except RateLimitError as e:
                retry_after = e.response.headers.get("Retry-After") if hasattr(e, "response") else None
                wait_time = float(retry_after) if retry_after else self.initial_backoff * (2 ** retries)
                retries += 1
                if retries >= self.max_retries:
                    raise
                await asyncio.sleep(wait_time)

    async def complete(self, messages: list[ChatMessage], **kwargs) -> GenerationResult:
        start_time = time.time()
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        async def _call():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                **kwargs
            )

        completion = await self._retry_with_exponential_backoff(_call)
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        input_tokens = completion.usage.prompt_tokens
        output_tokens = completion.usage.completion_tokens
        cost_usd = self._calculate_cost(input_tokens, output_tokens)

        return GenerationResult(
            content=completion.choices[0].message.content,
            model=completion.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            finish_reason=completion.choices[0].finish_reason
        )

    async def stream(self, messages: list[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        async def _call():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                stream=True,
                **kwargs
            )

        stream = await self._retry_with_exponential_backoff(_call)
        async for chunk in stream:  # type: ChatCompletionChunk
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]

            async def _call():
                return await self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )

            response = await self._retry_with_exponential_backoff(_call)
            batch_embeddings = [e.embedding for e in response.data]
            embeddings.extend(batch_embeddings)
        return embeddings

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * self.PRICE_TABLE[self.model]["input"]
        output_cost = (output_tokens / 1_000_000) * self.PRICE_TABLE[self.model]["output"]
        return input_cost + output_cost

    @property
    def cost_per_input_token(self) -> float:
        return self.PRICE_TABLE[self.model]["input"] / 1_000_000

    @property
    def cost_per_output_token(self) -> float:
        return self.PRICE_TABLE[self.model]["output"] / 1_000_000

    @property
    def context_window(self) -> int:
        return self.CONTEXT_WINDOWS[self.model]
