import hashlib
import json

from django.core.cache import cache


class DashboardCacheService:
    DEFAULT_TIMEOUT = 60

    @staticmethod
    def make_key(prefix: str, payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"

    @classmethod
    def get_or_set(cls, key: str, producer, timeout: int | None = None):
        cached = cache.get(key)
        if cached is not None:
            return cached
        value = producer()
        cache.set(key, value, timeout=timeout or cls.DEFAULT_TIMEOUT)
        return value

    @staticmethod
    def invalidate_prefix(prefix: str):
        # Works with RedisCache backend.
        try:
            cache.delete_pattern(f"{prefix}:*")
        except Exception:
            # Fallback when backend doesn't support delete_pattern.
            pass
