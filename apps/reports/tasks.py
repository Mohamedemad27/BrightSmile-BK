from celery import shared_task

from apps.users.models import User

from .services.export_service import ReportExportService
from .services.report_data_service import ReportDataService


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def generate_report_export_task(self, *, report_type, user_id, filters=None, file_format="csv"):
    user = User.objects.get(id=user_id)
    payload = ReportDataService.generate(
        report_type=report_type,
        user=user,
        filters=filters or {},
    )
    exported = ReportExportService.export_and_upload(
        report_type=report_type,
        payload=payload,
        fmt=file_format,
        task_id=self.request.id,
    )
    return {
        "status": "completed",
        "download_url": exported["download_url"],
        "object_key": exported["object_key"],
        "rows": exported["rows"],
        "report_type": report_type,
        "file_format": file_format,
    }
