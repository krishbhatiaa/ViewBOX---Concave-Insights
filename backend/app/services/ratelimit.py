"""Pluggable rate limiting for prototype and production deployments.

RateLimiter.allow(key, limit, window) is the interface used by auth endpoints.
InMemoryRateLimiter is the default and preserves single-worker behavior.
RedisRateLimiter documents the production swap: replace the in-process dict with
a shared Redis counter keyed by the same `key` and an expiring window.
"""
import os
import time
import logging

log = logging.getLogger("viewbox.ratelimit")


class RateLimiter:
    def allow(self, key: str, limit: int, window: int) -> bool:
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    """Current sliding-window behavior: per-process, per-key timestamps."""

    def __init__(self):
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int, window: int) -> bool:
        t = time.time()
        hits = [x for x in self._hits.get(key, []) if t - x < window]
        if len(hits) >= limit:
            return False
        self._hits[key] = hits + [t]
        return True

    def reset(self):
        self._hits.clear()


class RedisRateLimiter(RateLimiter):
    """Production swap: shared counters in Redis, e.g. INCR + EXPIRE per key/window.

    Wire a Redis client here when deploying behind multiple workers; no Redis
    dependency is bundled with the prototype.
    """

    def allow(self, key: str, limit: int, window: int) -> bool:
        raise NotImplementedError("Provide a Redis-backed RateLimiter for multi-worker deployments")


def build_rate_limiter() -> RateLimiter:
    backend = os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower()
    if backend == "memory":
        return InMemoryRateLimiter()
    if backend == "redis":
        return RedisRateLimiter()
    raise ValueError(f"Unknown RATE_LIMIT_BACKEND: {backend}")


rate_limiter = build_rate_limiter()


def warn_if_inmemory_multiworker(limiter: RateLimiter, workers: int):
    if isinstance(limiter, InMemoryRateLimiter) and workers > 1:
        log.warning("In-memory rate limiter is active with %s workers; use RATE_LIMIT_BACKEND=redis", workers)
