"""Small in-process rate-limiting baseline for the bounded v1.0 release.

The limiter is intentionally process-local. It protects one backend instance
against accidental bursts and simple abuse without introducing Redis solely for
release breadth. Cloud Run max-instance limits bound the aggregate exposure, but
this is not a globally consistent distributed rate limiter or DDoS control.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class InMemoryRateLimiter:
    """Thread-safe sliding-window limiter with bounded key memory."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._events: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def check(
        self,
        *,
        scope: str,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate-limit values must be positive integers.")

        now = self._clock()
        identity = (scope, key)
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._events.get(identity)
            if bucket is None:
                while len(self._events) >= self._max_keys:
                    self._events.popitem(last=False)
                bucket = deque()
                self._events[identity] = bucket
            else:
                self._events.move_to_end(identity)

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
                return RateLimitDecision(False, retry_after)

            bucket.append(now)
            return RateLimitDecision(True, 0)


rate_limiter = InMemoryRateLimiter()


def enforce_rate_limit(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Raise HTTP 429 when the configured process-local window is exhausted."""

    if not settings.rate_limit_enabled:
        return

    decision = rate_limiter.check(
        scope=scope,
        key=key,
        limit=limit,
        window_seconds=window_seconds,
    )
    if decision.allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please retry later.",
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )
