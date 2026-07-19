from uuid import UUID

import pytest
import structlog
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from config.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware


def test_request_context_middleware_adds_valid_request_id_header():
    request = RequestFactory().get("/api/v1/links/")

    middleware = RequestContextMiddleware(
        get_response=lambda request: HttpResponse(status=200)
    )

    response = middleware(request)

    request_id = response[REQUEST_ID_HEADER]
    parsed_request_id = UUID(request_id)

    assert str(parsed_request_id) == request_id


def test_request_context_is_bound_during_request():
    request = RequestFactory().post("/api/v1/links/")

    captured_context: dict[str, object] = {}

    def get_response(request: HttpRequest) -> HttpResponse:
        captured_context.update(structlog.contextvars.get_contextvars())
        return HttpResponse(status=200)

    middleware = RequestContextMiddleware(get_response=get_response)

    response = middleware(request)

    assert captured_context["request_id"] == response[REQUEST_ID_HEADER]
    assert captured_context["request_method"] == "POST"
    assert captured_context["request_path"] == "/api/v1/links/"


def test_request_context_is_cleared_after_request():
    structlog.contextvars.bind_contextvars(stale_value="should-not-survive")
    request = RequestFactory().get("/api/v1/links/")

    middleware = RequestContextMiddleware(
        get_response=lambda request: HttpResponse(status=200)
    )
    middleware(request)

    assert structlog.contextvars.get_contextvars() == {}


def test_request_context_is_cleared_when_response_raises():
    request = RequestFactory().get("/api/v1/links/")

    def get_response(request: HttpRequest) -> HttpResponse:
        raise RuntimeError("Unexpected failure")

    middleware = RequestContextMiddleware(get_response=get_response)
    with pytest.raises(RuntimeError, match="Unexpected failure"):
        middleware(request)

    assert structlog.contextvars.get_contextvars() == {}
