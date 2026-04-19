import uuid

from django.conf import settings
from django.db import models

from utils.soft_delete import SoftDeleteModel


class AuditLog(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_audit_logs",
    )
    action = models.CharField(max_length=120, db_index=True)
    target_type = models.CharField(max_length=100, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
        ]

    def __str__(self):
        return f"{self.action} ({self.target_type}:{self.target_id})"
