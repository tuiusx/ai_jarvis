import threading
import time


class CommandRateLimiter:
    def __init__(self, min_interval_seconds: float = 0.8):
        self.min_interval = max(0.0, float(min_interval_seconds))
        self._lock = threading.Lock()
        self._last_seen = 0.0

    def allow(self):
        if self.min_interval <= 0:
            return True, 0.0

        now = time.monotonic()
        with self._lock:
            delta = now - self._last_seen
            if delta < self.min_interval:
                return False, round(self.min_interval - delta, 3)
            self._last_seen = now
        return True, 0.0
