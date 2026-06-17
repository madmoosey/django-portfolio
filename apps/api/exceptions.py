from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Standardizes DRF error responses to a consistent format.
    Example: {"error": {"message": "Invalid input", "details": {...}, "code": "validation_error"}}
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            "error": {
                "message": getattr(exc, "default_detail", "A server error occurred."),
                "details": response.data,
                "code": getattr(exc, "default_code", "error"),
            }
        }
        # Clear original data and set custom
        response.data = custom_data

    return response
