import mimetypes
import json
from pathlib import Path

from django.conf import settings


class ReportStorageService:
    @staticmethod
    def upload(local_path: str, object_key: str) -> str:
        endpoint = getattr(settings, "REPORTS_STORAGE_ENDPOINT", "")
        bucket = getattr(settings, "REPORTS_STORAGE_BUCKET", "")
        access_key = getattr(settings, "REPORTS_STORAGE_ACCESS_KEY", "")
        secret_key = getattr(settings, "REPORTS_STORAGE_SECRET_KEY", "")
        if not endpoint or not bucket or not access_key or not secret_key:
            raise RuntimeError("MinIO/S3 settings are not configured.")

        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=getattr(settings, "REPORTS_STORAGE_REGION", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )
        # Ensure bucket exists in local MinIO/S3-compatible setups.
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)
        public_base = getattr(settings, "REPORTS_PUBLIC_BASE_URL", "").rstrip("/")
        if public_base:
            try:
                client.put_bucket_policy(
                    Bucket=bucket,
                    Policy=json.dumps(
                        {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Sid": "PublicReadGetObject",
                                    "Effect": "Allow",
                                    "Principal": "*",
                                    "Action": ["s3:GetObject"],
                                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                                }
                            ],
                        }
                    ),
                )
            except Exception:
                # If policy cannot be updated, fall back to presigned URLs below.
                pass
        ct, _ = mimetypes.guess_type(local_path)
        client.upload_file(
            local_path,
            bucket,
            object_key,
            ExtraArgs={"ContentType": ct or "application/octet-stream"},
        )
        if public_base:
            return f"{public_base}/{bucket}/{object_key}"
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=getattr(settings, "REPORTS_DOWNLOAD_URL_EXPIRY_SECONDS", 86400),
        )

    @staticmethod
    def extension_for(fmt: str) -> str:
        if fmt == "xlsx":
            return "xlsx"
        if fmt == "pdf":
            return "pdf"
        return "csv"

    @staticmethod
    def filename(report_type: str, fmt: str) -> str:
        ext = ReportStorageService.extension_for(fmt)
        return f"{report_type}.{ext}"

    @staticmethod
    def object_key(report_type: str, task_id: str, fmt: str) -> str:
        ext = ReportStorageService.extension_for(fmt)
        return f"reports/{report_type}/{task_id}.{ext}"

    @staticmethod
    def ensure_parent(path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
