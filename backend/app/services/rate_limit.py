import time
from collections import defaultdict

from app.config import settings


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        hits = [t for t in self._hits[key] if now - t < self.window]
        if len(hits) >= self.max_requests:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True


upload_limiter = RateLimiter(max_requests=10, window_seconds=3600)
