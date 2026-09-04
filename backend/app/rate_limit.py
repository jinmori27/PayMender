from __future__ import annotations

import math
import time
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException


@dataclass(slots=True)
class _Bucket:
    count: int
    reset_at: float
    last_seen: float


class FixedWindowRateLimiter:
    def __init__(self, max_keys: int = 10_000) -> None:
        self.max_keys = max_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def check(self, scope: str, client_key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        key = f"{scope}:{client_key}"
        with self._lock:
            expired = [name for name, bucket in self._buckets.items() if bucket.reset_at <= now]
            for name in expired:
                self._buckets.pop(name, None)
            if key not in self._buckets and len(self._buckets) >= self.max_keys:
                oldest = min(self._buckets, key=lambda name: self._buckets[name].last_seen)
                self._buckets.pop(oldest, None)

            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(count=0, reset_at=now + window_seconds, last_seen=now)
                self._buckets[key] = bucket
            if bucket.count >= limit:
                retry_after = max(1, math.ceil(bucket.reset_at - now))
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.count += 1
            bucket.last_seen = now
