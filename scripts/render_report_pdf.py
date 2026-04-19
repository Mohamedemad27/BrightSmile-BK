import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

    import django  # noqa: PLC0415

    django.setup()

    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from apps.reports.services.report_data_service import ReportDataService  # noqa: PLC0415
    from apps.reports.services.export_service import ReportExportService  # noqa: PLC0415

    report_types = sys.argv[1:] or ["doctor_appointments", "doctor_patients"]

    User = get_user_model()
    user = (
        User.objects.filter(user_type="doctor").order_by("created_at").first()
        or User.objects.filter(user_type="admin").order_by("created_at").first()
    )
    if not user:
        raise SystemExit("No doctor/admin user found to render reports.")

    out_dir = repo_root.parent / "Reports" / "_preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    for report_type in report_types:
        payload = ReportDataService.generate(
            report_type=report_type,
            user=user,
            filters={"limit": 50},
        )
        out_path = out_dir / f"{report_type}_preview.pdf"
        ReportExportService._render_pdf_to_file(
            report_type=report_type,
            payload=payload,
            output_path=str(out_path),
        )
        print(f"WROTE {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

