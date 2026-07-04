import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class _ClientWindow:
    timestamps: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """In-process, single-worker limiter. Allows up to `burst` requests instantly and
    caps sustained throughput at `requests_per_minute` over a rolling 60s window per
    client key. Not shared across processes/workers by design (see rate_limit.py docstring
    in the wiring code for the scope decision)."""

    def __init__(self, requests_per_minute: int, burst: int) -> None:
        self._requests_per_minute = max(requests_per_minute, 1)
        self._burst = max(burst, 1)
        self._window_seconds = 60.0
        self._clients: dict[str, _ClientWindow] = {}
        self._lock = asyncio.Lock()

    async def check(self, client_key: str) -> RateLimitResult:
        async with self._lock:
            now = time.monotonic()
            window = self._clients.setdefault(client_key, _ClientWindow())
            cutoff = now - self._window_seconds
            window.timestamps = [ts for ts in window.timestamps if ts > cutoff]

            limit = max(self._requests_per_minute, self._burst)
            if len(window.timestamps) >= limit:
                oldest = window.timestamps[0]
                retry_after = max(int(oldest + self._window_seconds - now) + 1, 1)
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

            window.timestamps.append(now)
            return RateLimitResult(allowed=True, retry_after_seconds=0)


def client_identity(user_email: str | None, client_host: str | None) -> str:
    if user_email:
        return f"email:{user_email.strip().lower()}"
    return f"ip:{client_host or 'unknown'}"
