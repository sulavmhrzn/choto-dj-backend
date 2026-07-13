from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def structured_exception_handler(
    exc: Exception, context: dict[str, Any]
) -> Response | None:
    response = exception_handler(exc, context)

    if response is None:
        return None

    original_data = response.data

    message = _get_error_message(status_code=response.status_code, data=original_data)
    errors = _get_error_details(original_data)

    response.data = {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors,
    }
    return response


def _get_error_message(*, status_code: int, data: Any) -> str:
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str):
            return detail

    default_messages = {
        400: "Validation failed.",
        401: "Authentication is required.",
        403: "You do not have permission to perform this action.",
        404: "The requested resource was not found.",
        405: "This request method is not allowed.",
        429: "Too many requests.",
    }

    return default_messages.get(status_code, "An error occured.")


def _get_error_details(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    errors = data.copy()
    errors.pop("detail", None)
    return errors or None
