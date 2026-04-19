import logging
import time
import uuid

logger = logging.getLogger("request")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.request_id = request_id
        start = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            user = getattr(request, "user", None)
            user_repr = getattr(user, "email", "anonymous") if getattr(user, "is_authenticated", False) else "anonymous"
            logger.exception(
                "request_id=%s user=%s method=%s path=%s status=500 duration_ms=%s",
                request_id,
                user_repr,
                request.method,
                request.path,
                duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        user = getattr(request, "user", None)
        user_repr = getattr(user, "email", "anonymous") if getattr(user, "is_authenticated", False) else "anonymous"

        response["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s user=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            user_repr,
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response
