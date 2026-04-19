import csv
import os
import re
import tempfile

from django.template.loader import render_to_string

from .storage_service import ReportStorageService


class ReportExportService:
    CSS_VAR_FALLBACKS = {
        "primary": "#2563eb",
        "primary-dark": "#1d4ed8",
        "primary-light": "#dbeafe",
        "secondary": "#0f172a",
        "accent": "#e8862a",
        "accent-light": "#fef3c7",
        "success": "#059669",
        "success-light": "#d1fae5",
        "danger": "#dc2626",
        "danger-light": "#fee2e2",
        "warning": "#d97706",
        "warning-light": "#fef3c7",
        "info": "#0891b2",
        "info-light": "#cffafe",
        "text-primary": "#1f2937",
        "text-secondary": "#6b7280",
        "text-muted": "#9ca3af",
        "border": "#e5e7eb",
        "border-dark": "#d1d5db",
        "bg-page": "#ffffff",
        "bg-subtle": "#f9fafb",
        "bg-muted": "#f3f4f6",
        "mti-blue": "#2b5ea7",
        "mti-orange": "#e8862a",
        "mti-gray": "#6b6b6b",
    }
    TABLE_KEY_BY_REPORT = {
        "admin_appointments": "appointments",
        "admin_audit": "audit_logs",
        "admin_doctors": "doctors",
        "admin_patients": "patients",
        "doctor_appointments": "appointments",
        "doctor_patients": "patients",
        "patient_report": "appointments",
    }

    TEMPLATE_BY_REPORT = {
        "admin_appointments": "reports/admin_appointments_report.html",
        "admin_audit": "reports/admin_audit_report.html",
        "admin_doctors": "reports/admin_doctors_report.html",
        "admin_patients": "reports/admin_patients_report.html",
        "doctor_appointments": "reports/doctor_appointments_report.html",
        "doctor_patients": "reports/doctor_patients_report.html",
        "patient_report": "reports/patient_report.html",
    }

    @staticmethod
    def _flatten(value, parent="", out=None):
        out = out or {}
        if isinstance(value, dict):
            for k, v in value.items():
                key = f"{parent}.{k}" if parent else str(k)
                ReportExportService._flatten(v, key, out)
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                out[parent] = "; ".join(str(v.get("name") or v.get("label") or v) for v in value)
            else:
                out[parent] = "; ".join(str(v) for v in value)
        else:
            out[parent] = value
        return out

    @classmethod
    def _rows(cls, report_type, payload):
        key = cls.TABLE_KEY_BY_REPORT.get(report_type)
        rows = payload.get(key) if key else None
        if not isinstance(rows, list):
            return []
        return [cls._flatten(r) for r in rows]

    @classmethod
    def _render_pdf_to_file(cls, *, report_type, payload, output_path):
        template_name = cls.TEMPLATE_BY_REPORT.get(report_type)
        if not template_name:
            raise RuntimeError(f"No report template configured for report_type '{report_type}'.")

        html = render_to_string(template_name, payload)

        # Prefer Chromium rendering (Playwright) to match the HTML template visuals
        # (flex/grid/SVG charts, advanced CSS, etc.). Fall back to xhtml2pdf if
        # Playwright/Chromium isn't available.
        engine = (os.getenv("REPORTS_PDF_ENGINE") or "chromium").strip().lower()
        if engine in ("chromium", "playwright", "chrome"):
            try:
                cls._render_pdf_with_playwright(html=html, output_path=output_path)
                return
            except Exception:
                # Fallback below
                pass

        html = cls._sanitize_html_for_xhtml2pdf(html)
        try:
            from xhtml2pdf import pisa
        except Exception as exc:
            raise RuntimeError("xhtml2pdf is required for pdf export.") from exc

        with open(output_path, "wb") as out:
            result = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
        if result.err:
            raise RuntimeError("Failed to generate PDF from report template.")

    @staticmethod
    def _render_pdf_with_playwright(*, html, output_path):
        """
        Render HTML -> PDF using headless Chromium (Playwright).
        This path supports modern CSS and SVG, matching the templates closely.
        """
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("playwright is required for Chromium PDF export.") from exc

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
            tmp.write(html)
            html_path = tmp.name

        try:
            file_url = f"file://{html_path}"
            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--no-sandbox"])
                try:
                    page = browser.new_page()
                    page.goto(file_url, wait_until="load")
                    page.emulate_media(media="print")
                    page.pdf(
                        path=output_path,
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    )
                finally:
                    browser.close()
        finally:
            try:
                os.unlink(html_path)
            except Exception:
                pass

    @staticmethod
    def _sanitize_html_for_xhtml2pdf(html):
        """
        xhtml2pdf does not support nested @page rules (e.g. @bottom-center).
        Keep simple @page { ... } blocks but strip nested rules inside them.
        Also strip @page :first if it only overrides margin/footer.
        Then replace all var(--xxx) with hardcoded fallback colors.
        """
        text = html

        def _strip_nested_at_page(match):
            block = match.group(0)
            if "@bottom-center" in block or "@top-center" in block:
                lines = []
                inside = False
                for line in block.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("@bottom-center") or stripped.startswith("@top-center"):
                        inside = True
                        continue
                    if inside:
                        if "}" in stripped:
                            inside = False
                        continue
                    lines.append(line)
                result = "\n".join(lines)
                result = re.sub(r"\{\s*\}", "", result)
                return result
            if ":first" in match.group(0) and "margin" in match.group(0):
                return ""
            return block

        text = re.sub(r"@page\s*[^{]*\{[^}]*(?:\{[^}]*\}[^}]*)*\}", _strip_nested_at_page, text, flags=re.DOTALL)

        def _replace_var(match):
            var_name = (match.group(1) or "").strip()
            return ReportExportService.CSS_VAR_FALLBACKS.get(var_name, "#000000")

        text = re.sub(r"var\(--([a-zA-Z0-9\-]+)\)", _replace_var, text)
        text = re.sub(r"@media\s+print\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}", "", text, flags=re.DOTALL)
        return text

    @classmethod
    def export_and_upload(cls, *, report_type, payload, fmt, task_id):
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ReportStorageService.extension_for(fmt)}") as tmp:
            path = tmp.name

        if fmt == "pdf":
            cls._render_pdf_to_file(report_type=report_type, payload=payload, output_path=path)
            rows_count = len(payload.get(cls.TABLE_KEY_BY_REPORT.get(report_type, ""), []))
        else:
            rows = cls._rows(report_type, payload)
            if not rows:
                rows = [cls._flatten(payload)]
            headers = sorted({k for row in rows for k in row.keys()})

            if fmt == "xlsx":
                try:
                    from openpyxl import Workbook
                except Exception as exc:
                    raise RuntimeError("openpyxl is required for xlsx export.") from exc
                wb = Workbook()
                ws = wb.active
                ws.title = "report"
                ws.append(headers)
                for row in rows:
                    ws.append([row.get(h, "") for h in headers])
                wb.save(path)
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({h: row.get(h, "") for h in headers})
            rows_count = len(rows)

        key = ReportStorageService.object_key(report_type, task_id, fmt)
        url = ReportStorageService.upload(path, key)
        return {"download_url": url, "object_key": key, "rows": rows_count}
