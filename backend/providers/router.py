import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from .anthropic_provider import AnthropicProvider
from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider


@dataclass
class RoutingCriteria:
    task_type: str  # "rag_generation" | "evaluation" | "embedding" | "classification"
    max_cost_per_call: float | None = None
    require_vision: bool = False
    require_long_context: bool = False  # > 32k tokens
    latency_budget_ms: int | None = None
    prefer_fine_tuned: bool = False


class ModelRouter:
    def __init__(self, redis_client: Redis) -> None:
        self.redis_client = redis_client
        self._model_registry_key = "router:models"
        self._default_models = [
            {
                "name": "gpt-4o-mini",
                "provider": "openai",
                "capabilities": ["text", "vision"],
                "context_window": 128000,
                "is_fine_tuned": False,
                "estimated_latency_ms": 500,
                "cost_per_input_token": 0.15 / 1_000_000,
                "cost_per_output_token": 0.60 / 1_000_000,
            },
            {
                "name": "gpt-4o",
                "provider": "openai",
                "capabilities": ["text", "vision"],
                "context_window": 128000,
                "is_fine_tuned": False,
                "estimated_latency_ms": 1500,
                "cost_per_input_token": 2.50 / 1_000_000,
                "cost_per_output_token": 10.00 / 1_000_000,
            },
            {
                "name": "claude-3-haiku-20240307",
                "provider": "anthropic",
                "capabilities": ["text"],
                "context_window": 200000,
                "is_fine_tuned": False,
                "estimated_latency_ms": 400,
                "cost_per_input_token": 0.25 / 1_000_000,
                "cost_per_output_token": 1.25 / 1_000_000,
            },
            {
                "name": "claude-3-sonnet-20240229",
                "provider": "anthropic",
                "capabilities": ["text", "vision"],
                "context_window": 200000,
                "is_fine_tuned": False,
                "estimated_latency_ms": 1200,
                "cost_per_input_token": 3.00 / 1_000_000,
                "cost_per_output_token": 15.00 / 1_000_000,
            },
        ]
        self._providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
        }

    async def get_registered_models(self) -> list[dict[str, Any]]:
        models_json = await self.redis_client.get(self._model_registry_key)
        if models_json:
            return json.loads(models_json)
        else:
            await self.redis_client.set(self._model_registry_key, json.dumps(self._default_models))
            return self._default_models

    async def route(self, criteria: RoutingCriteria) -> tuple[BaseLLMProvider, str]:
        """Route to appropriate provider and model based on criteria, returns (provider_instance, model_name)"""
        models = await self.get_registered_models()
        filtered = models.copy()

        # Rule 1: Require vision
        if criteria.require_vision:
            filtered = [m for m in filtered if "vision" in m["capabilities"]]

        # Rule 2: Require long context
        if criteria.require_long_context:
            filtered = [m for m in filtered if m["context_window"] > 100000]

        # Rule 3: Prefer fine-tuned
        if criteria.prefer_fine_tuned:
            fine_tuned = [m for m in filtered if m["is_fine_tuned"] and m.get("task_type") == criteria.task_type]
            if fine_tuned:
                filtered = fine_tuned

        # Rule 4: Evaluation task always uses capable judge, never fine-tuned
        if criteria.task_type == "evaluation":
            filtered = [m for m in filtered if not m["is_fine_tuned"] and "gpt-4o" in m["name"] or "sonnet" in m["name"] or "opus" in m["name"]]

        # Rule 5: Max cost per call (simple estimate)
        if criteria.max_cost_per_call:
            filtered = [m for m in filtered if (m["cost_per_input_token"] * 10000) + (m["cost_per_output_token"] * 1000) < criteria.max_cost_per_call]

        # Default: Cheapest remaining model
        if not filtered:
            raise ValueError("No models available that satisfy the given criteria")
        
        filtered.sort(key=lambda m: m["cost_per_input_token"] + m["cost_per_output_token"])
        selected = filtered[0]
        
        provider_cls = self._providers[selected["provider"]]
        provider = provider_cls(model=selected["name"])
        return provider, selected["name"]

    async def register_model(self, model_config: dict[str, Any]) -> None:
        models = await self.get_registered_models()
        # Replace if name exists
        models = [m for m in models if m["name"] != model_config["name"]]
        models.append(model_config)
        await self.redis_client.set(self._model_registry_key, json.dumps(models))
