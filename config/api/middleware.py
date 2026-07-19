from collections.abc import Callable
from uuid import uuid4

import structlog
from django.http import HttpRequest, HttpResponse

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        structlog.contextvars.clear_contextvars()

        request_id = str(uuid4())

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            request_method=request.method,
            request_path=request.path,
        )

        request.request_id = request_id
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()
