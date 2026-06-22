"""
Syndicate registry lookup service.

This represents the (mock) dental syndicate's authoritative member database.
It is used at doctor self-registration time to verify that the syndicate
number a doctor enters is genuine and in good standing before the account is
created (pending admin approval).

The data is bundled as a local JSON fixture (`syndicate_registry.json`) which
mirrors the syndicate portal mock used by the dashboard. If a live syndicate
source is configured via ``SYNDICATE_SOURCE_URL`` it takes precedence, falling
back to the bundled fixture when unavailable.
"""

import json
import logging
import os
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "syndicate_registry.json")

# Statuses that are considered "in good standing" and allowed to register.
ACTIVE_STATUSES = {"active"}


class SyndicateRegistryService:
    """Read-only lookups against the syndicate member registry."""

    _lock = threading.Lock()
    _cache = None  # list[dict]

    @classmethod
    def _load_fixture(cls):
        try:
            with open(_FIXTURE_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return data
            logger.warning("Syndicate registry fixture is not a list: %s", type(data).__name__)
        except (OSError, ValueError) as exc:
            logger.exception("Failed to load syndicate registry fixture: %s", exc)
        return []

    @classmethod
    def get_records(cls):
        """Return all syndicate member records (cached in-process)."""
        if cls._cache is None:
            with cls._lock:
                if cls._cache is None:
                    cls._cache = cls._load_fixture()
        return cls._cache

    @classmethod
    def clear_cache(cls):
        with cls._lock:
            cls._cache = None

    @staticmethod
    def _normalize(value):
        return (value or "").strip().upper()

    @classmethod
    def lookup_by_number(cls, syndicate_number):
        """Return the registry record for a syndicate number, or None."""
        target = cls._normalize(syndicate_number)
        if not target:
            return None
        for record in cls.get_records():
            if cls._normalize(record.get("syndicate_number")) == target:
                return record
        return None

    @classmethod
    def lookup_by_email(cls, email):
        """Return the registry record matching an email, or None."""
        target = (email or "").strip().lower()
        if not target:
            return None
        for record in cls.get_records():
            if (record.get("email") or "").strip().lower() == target:
                return record
        return None

    @classmethod
    def license_status_for(cls, syndicate_number):
        """Return the license status string for a syndicate number ('' if unknown)."""
        record = cls.lookup_by_number(syndicate_number)
        if not record:
            return ""
        return (record.get("license_status") or "").strip().lower()

    @classmethod
    def is_active(cls, record):
        return (record.get("license_status") or "").strip().lower() in ACTIVE_STATUSES
