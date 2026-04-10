from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Wraps all DRF errors in {error: {code, message, field}} envelope.
    Never returns bare root objects or raw Django HTML errors.
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            "error": {
                "code": _get_error_code(exc),
                "message": _get_error_message(response.data),
                "field": _get_error_field(response.data),
            }
        }
        response.data = error_data

    return response


def _get_error_code(exc) -> str:
    from rest_framework.exceptions import NotAuthenticated, PermissionDenied, NotFound
    mapping = {
        NotAuthenticated: "UNAUTHENTICATED",
        PermissionDenied: "FORBIDDEN",
        NotFound: "NOT_FOUND",
    }
    return mapping.get(type(exc), "VALIDATION_ERROR")


def _get_error_message(data) -> str:
    if isinstance(data, dict):
        for key in ("detail", "non_field_errors"):
            if key in data:
                val = data[key]
                return str(val[0]) if isinstance(val, list) else str(val)
        values = list(data.values())
        return str(values[0]) if values else "Unknown error"
    if isinstance(data, list):
        return str(data[0])
    return str(data)


def _get_error_field(data) -> str | None:
    if isinstance(data, dict) and "detail" not in data:
        field = next((k for k in data if k != "non_field_errors"), None)
        return field
    return None
