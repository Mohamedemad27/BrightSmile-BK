from django.conf import settings


def is_feature_enabled(flag_name: str, default: bool = False) -> bool:
    flags = getattr(settings, "FEATURE_FLAGS", {})
    return bool(flags.get(flag_name, default))
