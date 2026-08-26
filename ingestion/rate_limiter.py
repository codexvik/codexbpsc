"""Simple per-source politeness rate limiter (tech architecture doc, section 4, step 5)."""

import threading
import time


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self.min_interval_seconds = min_interval_seconds
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def wait(self):
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
            self._last_request_at = time.monotonic()
