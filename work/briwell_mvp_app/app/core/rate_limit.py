import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class _ClientWindow:
    timestamps: list[float] = field(default_factory=list)
    burst_timestamps: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """In-process, single-worker limiter. Allows up to `burst` requests per second and
    caps sustained throughput at `requests_per_minute` over a rolling 60s window per
    client key. Not shared across processes/workers by design (see rate_limit.py docstring
    in the wiring code for the scope decision)."""

    # Client keys are caller-controlled (email header or IP), so entries are swept once
    # both windows go empty to avoid unbounded growth over a long-running process.
    _SWEEP_INTERVAL = 500

    def __init__(self, requests_per_minute: int, burst: int) -> None:
        self._requests_per_minute = max(requests_per_minute, 1)
        self._burst = max(burst, 1)
        self._window_seconds = 60.0
        self._burst_window_seconds = 1.0
        self._clients: dict[str, _ClientWindow] = {}
        self._lock = asyncio.Lock()
        self._checks_since_sweep = 0

    async def check(self, client_key: str) -> RateLimitResult:
        async with self._lock:
            now = time.monotonic()
            window = self._clients.setdefault(client_key, _ClientWindow())
            cutoff = now - self._window_seconds
            window.timestamps = [ts for ts in window.timestamps if ts > cutoff]

            burst_cutoff = now - self._burst_window_seconds
            window.burst_timestamps = [ts for ts in window.burst_timestamps if ts > burst_cutoff]

            if len(window.burst_timestamps) >= self._burst:
                retry_after = max(int(self._burst_window_seconds), 1)
                self._sweep_stale_clients()
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

            if len(window.timestamps) >= self._requests_per_minute:
                oldest = window.timestamps[0]
                retry_after = max(int(oldest + self._window_seconds - now) + 1, 1)
                self._sweep_stale_clients()
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

            window.timestamps.append(now)
            window.burst_timestamps.append(now)
            self._sweep_stale_clients()
            return RateLimitResult(allowed=True, retry_after_seconds=0)

    def _sweep_stale_clients(self) -> None:
        self._checks_since_sweep += 1
        if self._checks_since_sweep < self._SWEEP_INTERVAL:
            return
        self._checks_since_sweep = 0
        stale_keys = [
            key
            for key, window in self._clients.items()
            if not window.timestamps and not window.burst_timestamps
        ]
        for key in stale_keys:
            del self._clients[key]


def client_identity(user_email: str | None, client_host: str | None) -> str:
    if user_email:
        return f"email:{user_email.strip().lower()}"
    return f"ip:{client_host or 'unknown'}"
