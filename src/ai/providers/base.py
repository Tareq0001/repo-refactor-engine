"""
AI Provider Abstraction Layer

Provides a unified interface for multiple AI providers (Anthropic Claude,
OpenAI GPT, Google Gemini, local Ollama). Includes automatic retry with
exponential backoff, rate limiting, token counting, and cost tracking.
"""
import asyncio
import time
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from src.ai.cache.semantic_cache import SemanticCache


@dataclass
class AIResponse:
    """Standardized response from any AI provider."""
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    cached: bool = False


@dataclass
class UsageTracker:
    """Tracks cumulative API usage across the migration."""
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    cache_hits: int = 0
    errors: int = 0
    requests_per_model: Dict[str, int] = field(default_factory=dict)

    def record(self, response: AIResponse):
        self.total_requests += 1
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost_usd += response.cost_usd
        self.total_latency_ms += response.latency_ms
        if response.cached:
            self.cache_hits += 1
        self.requests_per_model[response.model] = self.requests_per_model.get(response.model, 0) + 1


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str, model: str, max_retries: int = 3):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.cache = SemanticCache()
        self.usage = UsageTracker()

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    async def _call_api(self, messages: List[Dict], temperature: float, max_tokens: int) -> AIResponse:
        ...

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        use_cache: bool = True,
    ) -> AIResponse:
        """Generate a response with caching, retry, and usage tracking."""
        # Check cache
        cache_key = self._cache_key(system_prompt, user_prompt, self.model)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                response = AIResponse(content=cached, model=self.model, provider=self.provider_name, cached=True)
                self.usage.record(response)
                return response

        # Retry with exponential backoff
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                start = time.monotonic()
                response = await self._call_api(messages, temperature, max_tokens)
                response.latency_ms = (time.monotonic() - start) * 1000
                response.cost_usd = self._estimate_cost(response.input_tokens, response.output_tokens)

                # Cache the response
                if use_cache:
                    self.cache.set(cache_key, response.content)

                self.usage.record(response)
                return response

            except Exception as e:
                last_error = e
                self.usage.errors += 1
                wait_time = (2 ** attempt) + 0.5
                await asyncio.sleep(wait_time)

        raise RuntimeError(f"AI provider {self.provider_name} failed after {self.max_retries} retries: {last_error}")

    def _cache_key(self, system: str, user: str, model: str) -> str:
        raw = f"{model}:{system[:200]}:{user[:500]}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @abstractmethod
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        ...


class AnthropicProvider(AIProvider):
    """Claude (Anthropic) provider for architectural comprehension."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def _call_api(self, messages: List[Dict], temperature: float, max_tokens: int) -> AIResponse:
        # In production: uses anthropic.AsyncAnthropic client
        # Simulated for scaffolding
        return AIResponse(
            content="[Claude architectural analysis would appear here]",
            model=self.model,
            provider=self.provider_name,
            input_tokens=len(messages[1]["content"].split()) * 2,
            output_tokens=500,
        )

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Claude Sonnet pricing: $3/M input, $15/M output
        return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)


class OpenAIProvider(AIProvider):
    """GPT-4/Codex (OpenAI) provider for code translation."""

    @property
    def provider_name(self) -> str:
        return "openai"

    async def _call_api(self, messages: List[Dict], temperature: float, max_tokens: int) -> AIResponse:
        # In production: uses openai.AsyncOpenAI client
        return AIResponse(
            content="[GPT-4 code translation would appear here]",
            model=self.model,
            provider=self.provider_name,
            input_tokens=len(messages[1]["content"].split()) * 2,
            output_tokens=800,
        )

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # GPT-4o pricing: $2.50/M input, $10/M output
        return (input_tokens * 2.5 / 1_000_000) + (output_tokens * 10.0 / 1_000_000)


class OllamaProvider(AIProvider):
    """Local Ollama provider for air-gapped environments (free, no API key)."""

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def _call_api(self, messages: List[Dict], temperature: float, max_tokens: int) -> AIResponse:
        # In production: calls http://localhost:11434/api/chat
        return AIResponse(
            content="[Local Ollama response would appear here]",
            model=self.model,
            provider=self.provider_name,
            input_tokens=0,
            output_tokens=0,
        )

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0  # Free (local inference)
