import logging

from app.services.ratelimit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    build_rate_limiter,
    warn_if_inmemory_multiworker,
)


def test_inmemory_limiter_matches_sliding_window_behavior():
    limiter = InMemoryRateLimiter()
    assert [limiter.allow("otp:1.2.3.4", 2, 60) for _ in range(3)] == [True, True, False]
    limiter.reset()
    assert limiter.allow("otp:1.2.3.4", 2, 60) is True


def test_rate_limiter_backend_is_selectable(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    assert isinstance(build_rate_limiter(), InMemoryRateLimiter)
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    assert isinstance(build_rate_limiter(), RedisRateLimiter)


def test_multiworker_warning_only_for_inmemory(monkeypatch, caplog):
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    with caplog.at_level(logging.WARNING, logger="viewbox.ratelimit"):
        warn_if_inmemory_multiworker(InMemoryRateLimiter(), 2)
        warn_if_inmemory_multiworker(RedisRateLimiter(), 2)
    assert "2 workers" in caplog.text
    assert "RATE_LIMIT_BACKEND=redis" in caplog.text
