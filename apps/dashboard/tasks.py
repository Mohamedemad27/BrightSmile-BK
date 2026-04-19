from celery import shared_task

from apps.dashboard.services import AuditService, SyndicateSyncService
from apps.users.models import User
from utils.feature_flags import is_feature_enabled


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_syndicate_task(self, payload=None, triggered_by_user_id=None):
    if not is_feature_enabled("enable_syndicate_sync", default=True):
        return {"status": "disabled"}

    normalized_payload = payload or SyndicateSyncService.fetch_external_payload()
    result = SyndicateSyncService.sync(normalized_payload)

    if is_feature_enabled("enable_audit_logging", default=True):
        user = None
        if triggered_by_user_id:
            user = User.objects.filter(id=triggered_by_user_id).first()
        AuditService.log_action(
            user=user,
            action="syndicate_synced_async",
            target_type="Syndicate",
            target_id="celery-task",
            description="Syndicate sync executed asynchronously.",
            metadata=result,
        )

    return result
