import json
import time
from typing import Any

from .config import settings

try:
    import redis
except ModuleNotFoundError:
    redis = None


class RedisClient:
    def __init__(self):
        self.client = (
            redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
            if redis
            else None
        )
        self.enabled = self.client is not None
        # In-memory fallback: {key: (expires_at_monotonic, value)}
        self._mem: dict[str, tuple[float, Any]] = {}

    def _disable(self):
        self.enabled = False
        self.client = None

    def get(self, key: str) -> Any | None:
        if self.enabled and self.client is not None:
            try:
                value = self.client.get(key)
                return json.loads(value) if value else None
            except Exception:
                self._disable()

        # Fallback to in-memory cache
        entry = self._mem.get(key)
        if entry:
            expires_at, value = entry
            if time.monotonic() < expires_at:
                return value
            del self._mem[key]
        return None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        if self.enabled and self.client is not None:
            try:
                self.client.setex(key, expire, json.dumps(value))
                return True
            except Exception:
                self._disable()

        # Fallback to in-memory cache (cap at 500 keys to avoid unbounded growth)
        if len(self._mem) >= 500:
            now = time.monotonic()
            self._mem = {k: v for k, v in self._mem.items() if v[0] > now}
        self._mem[key] = (time.monotonic() + expire, value)
        return True

    def delete(self, key: str) -> bool:
        self._mem.pop(key, None)
        if not self.enabled or self.client is None:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception:
            self._disable()
            return False


redis_client = RedisClient()
