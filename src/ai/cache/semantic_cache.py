"""
Semantic Cache — LRU + Hash-based Prompt Caching

Caches AI responses to avoid redundant API calls for identical or
near-identical prompts. Uses SHA-256 hashing with an LRU eviction policy.
In production, this would be backed by Redis for persistence across runs.
"""
import json
import time
from collections import OrderedDict
from typing import Optional
from dataclasses import dataclass


@dataclass
class CacheEntry:
    content: str
    created_at: float
    hit_count: int = 0
    ttl_seconds: float = 3600  # 1 hour default


class SemanticCache:
    """
    In-memory LRU cache for AI API responses.
    Keyed by SHA-256 hash of (model + system_prompt + user_prompt).
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Optional[str]:
        """Retrieve a cached response, or None if not found/expired."""
        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]

        # Check TTL
        if time.time() - entry.created_at > entry.ttl_seconds:
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hit_count += 1
        self._stats["hits"] += 1
        return entry.content

    def set(self, key: str, content: str, ttl: Optional[float] = None):
        """Cache a response."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key].content = content
            return

        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
            self._stats["evictions"] += 1

        self._cache[key] = CacheEntry(
            content=content,
            created_at=time.time(),
            ttl_seconds=ttl or self._default_ttl,
        )

    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            **self._stats,
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate": self._stats["hits"] / max(self._stats["hits"] + self._stats["misses"], 1) * 100,
        }
