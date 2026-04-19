import logging

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from apps.users.models import Doctor

logger = logging.getLogger(__name__)


class SyndicateSyncService:
    DEACTIVATE_STATUSES = {"suspended", "revoked", "expired"}

    @classmethod
    def _session(cls):
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    @classmethod
    def fetch_external_payload(cls):
        endpoint = getattr(settings, "SYNDICATE_SOURCE_URL", "").strip()
        if not endpoint:
            return []

        timeout = float(getattr(settings, "SYNDICATE_TIMEOUT_SECONDS", 5))
        try:
            response = cls._session().get(endpoint, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                return payload
            logger.warning("Unexpected syndicate payload shape: %s", type(payload).__name__)
        except requests.RequestException as exc:
            logger.exception("Failed to fetch syndicate payload: %s", exc)
        return []

    @classmethod
    def sync(cls, payload):
        updated = 0
        deactivated = 0
        not_found = 0

        for item in payload:
            email = (item.get("email") or "").strip().lower()
            if not email:
                continue

            try:
                doctor = Doctor.objects.select_related("user").get(user__email__iexact=email)
            except Doctor.DoesNotExist:
                not_found += 1
                continue

            user = doctor.user
            license_status = (item.get("license_status") or "").strip().lower()
            should_deactivate = license_status in cls.DEACTIVATE_STATUSES

            if should_deactivate and user.is_active:
                user.is_active = False
                user.save(update_fields=["is_active", "updated_at"])
                deactivated += 1

            dirty = []
            specialty = item.get("specialty")
            if isinstance(specialty, str) and specialty and specialty != doctor.specialty:
                doctor.specialty = specialty
                dirty.append("specialty")

            location = item.get("location")
            if isinstance(location, str) and location and location != doctor.location:
                doctor.location = location
                dirty.append("location")

            if dirty:
                dirty.append("updated_at")
                doctor.save(update_fields=dirty)

            updated += 1

        logger.info(
            "Syndicate sync completed: updated=%s deactivated=%s not_found=%s",
            updated,
            deactivated,
            not_found,
        )
        return {"updated": updated, "deactivated": deactivated, "not_found": not_found}
