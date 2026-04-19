from rest_framework import status
from rest_framework.response import Response


def api_success(data=None, message="", status_code=status.HTTP_200_OK):
    return Response(
        {
            "data": data,
            "error": None,
            "message": message,
        },
        status=status_code,
    )


def api_created(data=None, message="Created successfully."):
    return api_success(data=data, message=message, status_code=status.HTTP_201_CREATED)


def api_updated(data=None, message="Updated successfully."):
    return api_success(data=data, message=message, status_code=status.HTTP_200_OK)


def api_deleted(message="Deleted successfully."):
    return api_success(data=None, message=message, status_code=status.HTTP_200_OK)


def api_error(message, error=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            "data": None,
            "error": error or {"detail": message},
            "message": message,
        },
        status=status_code,
    )
