from django.db.models import Q

from apps.dashboard.models import AuditLog
from utils.feature_flags import is_feature_enabled


class AuditService:
    @staticmethod
    def log_action(*, user, action, target_type="", target_id="", description="", metadata=None, ip_address=None):
        if not is_feature_enabled("enable_audit_logging", default=True):
            return None
        return AuditLog.objects.create(
            user=user,
            action=action,
            target_type=target_type or "",
            target_id=str(target_id or ""),
            description=description or "",
            metadata=metadata or {},
            ip_address=ip_address,
        )

    @classmethod
    def get_entries_queryset(cls, *, search="", action="", date_from=None, date_to=None):
        qs = (
            AuditLog.objects
            .select_related("user")
            .only(
                "id",
                "action",
                "target_type",
                "target_id",
                "description",
                "ip_address",
                "metadata",
                "created_at",
                "user__email",
                "user__first_name",
                "user__last_name",
            )
            .order_by("-created_at")
        )

        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(description__icontains=search)
                | Q(target_type__icontains=search)
            )

        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if action:
            qs = qs.filter(action=action)

        return qs
