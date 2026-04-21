"""
Audit-logging middleware.

Logs every successful authenticated API write (POST/PATCH/PUT/DELETE) under
`/api/` into `dashboard.AuditLog`. Explicit `AuditService.log_action` calls
inside admin views still work — the middleware skips requests that have
already been audited in the same response cycle via `request._audit_logged`.
"""

from __future__ import annotations

import logging
import re

from apps.dashboard.services import AuditService

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

# Skip pure infrastructure / polling paths that would flood the audit table.
_PATH_SKIP = re.compile(r"^/api/(v\d+/)?(health|schema|docs|redoc|ai/smile-preview/[0-9a-f-]+)/?$")


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _derive_action(method: str, path: str) -> tuple[str, str]:
    """Return (action, target_type) derived from the request path."""
    stripped = path.strip("/").lstrip("api/").lstrip("v1/").strip("/")
    segments = [s for s in stripped.split("/") if s]
    # Drop UUIDs / numeric IDs for a cleaner action code
    segments = [s for s in segments if not re.fullmatch(r"[0-9a-fA-F-]{8,}", s)]
    target_type = segments[0] if segments else "unknown"
    tail = segments[-1] if len(segments) > 1 else ""
    action = f"{method.lower()}_{'_'.join(segments)}" if segments else method.lower()
    return action, target_type or tail


class AuditLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception:  # pragma: no cover — never break requests on logging failure
            logger.exception("Audit logging failed")
        return response

    def _maybe_log(self, request, response):
        if getattr(request, "_audit_logged", False):
            return
        if request.method not in WRITE_METHODS:
            return
        if response.status_code >= 400:
            return
        path = request.path or ""
        if not path.startswith("/api/"):
            return
        if _PATH_SKIP.match(path):
            return

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return

        action, target_type = _derive_action(request.method, path)
        AuditService.log_action(
            user=user,
            action=action,
            target_type=target_type,
            target_id="",
            description=f"{request.method} {path}",
            ip_address=_client_ip(request),
            metadata={"status_code": response.status_code},
        )
