from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        return None

    detail = response.data
    message = "Request failed."
    if isinstance(detail, dict):
        message = detail.get("detail", message)
    elif isinstance(detail, list):
        message = "Validation failed."
    elif isinstance(detail, str):
        message = detail

    response.data = {
        "data": None,
        "error": detail,
        "message": str(message),
    }
    return response
