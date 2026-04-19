import hashlib
import json
from functools import wraps

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response


def _request_hash(request):
    body = request.body or b""
    raw = f"{request.method}:{request.path}:{body.decode('utf-8', errors='ignore')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_key(request, idem_key):
    user_id = getattr(request.user, "id", "anonymous")
    base = f"idem:{user_id}:{request.path}:{idem_key}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def idempotent_endpoint(timeout_seconds=60 * 60):
    """
    Idempotency-Key behavior for critical POST endpoints.
    - first request stores hash + status + body
    - repeated same key+same payload returns saved response
    - repeated same key+different payload returns 409
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(view, request, *args, **kwargs):
            idem_key = request.headers.get("Idempotency-Key")
            if not idem_key:
                return view_func(view, request, *args, **kwargs)

            key = _cache_key(request, idem_key)
            req_hash = _request_hash(request)
            cached = cache.get(key)

            if cached is not None:
                if cached.get("request_hash") != req_hash:
                    return Response(
                        {
                            "data": None,
                            "error": {"detail": "Idempotency key reuse with different payload."},
                            "message": "Conflict",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response(cached.get("response"), status=cached.get("status", status.HTTP_200_OK))

            response = view_func(view, request, *args, **kwargs)
            if isinstance(response, Response):
                cache.set(
                    key,
                    {
                        "request_hash": req_hash,
                        "status": response.status_code,
                        "response": response.data,
                    },
                    timeout=timeout_seconds,
                )
            return response

        return wrapped

    return decorator
