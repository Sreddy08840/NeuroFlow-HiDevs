import asyncio
import time
from typing import AsyncGenerator
from anthropic import AsyncAnthropic
from .base import BaseLLMProvider, ChatMessage, GenerationResult
from config import settings
from resilience.circuit_breaker import CircuitBreaker
from resilience.timeout_manager import TimeoutManager
from resilience.rate_limiter import RateLimiter


class AnthropicProvider(BaseLLMProvider):
    PRICE_TABLE = {
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    }

    CONTEXT_WINDOWS = {
        "claude-3-haiku-20240307": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-opus-20240229": 200000,
    }

    def __init__(self, api_key: str = None, model: str = "claude-3-haiku-20240307"):
        self.client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model
        self.circuit_breaker = CircuitBreaker("anthropic")
        self.timeout_manager = TimeoutManager()
        self.rate_limiter = RateLimiter()

    async def complete(self, messages: list[ChatMessage], **kwargs) -> GenerationResult:
        # Check rate limits
        allowed, wait = await self.rate_limiter.check_provider_rate_limit("anthropic")
        if not allowed:
            await asyncio.sleep(wait)
        
        start_time = time.time()
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        call_kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 4096,
            **kwargs
        }

        if system_message:
            call_kwargs["system"] = system_message

        async with self.circuit_breaker:
            completion = await self.timeout_manager.execute_with_timeout(
                "chat_completion",
                self.client.messages.create(**call_kwargs)
            )
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        input_tokens = completion.usage.input_tokens
        output_tokens = completion.usage.output_tokens
        cost_usd = self._calculate_cost(input_tokens, output_tokens)

        return GenerationResult(
            content="".join([block.text for block in completion.content if block.type == "text"]),
            model=completion.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            finish_reason=completion.stop_reason
        )

    async def stream(self, messages: list[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:
        # Check rate limits
        allowed, wait = await self.rate_limiter.check_provider_rate_limit("anthropic")
        if not allowed:
            await asyncio.sleep(wait)
        
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        call_kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 4096,
            **kwargs
        }

        if system_message:
            call_kwargs["system"] = system_message

        async with self.circuit_breaker:
            async with self.timeout_manager.execute_with_timeout(
                "chat_completion",
                self.client.messages.stream(**call_kwargs)
            ) as stream:
            async for text in stream.text_stream:
                yield text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not provide an embedding API yet")

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
