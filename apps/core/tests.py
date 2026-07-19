import pytest
from allauth.headless.base.views import APIView
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def test_liveness_returns_ok(api_client: APIClient) -> None:
    response = api_client.get(
        reverse("core:health-live"),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "status": "ok",
    }


@pytest.mark.django_db
def test_readiness_returns_ok_when_dependencies_are_available(
    api_client: APIClient,
) -> None:
    response = api_client.get(
        reverse("core:health-ready"),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "status": "ok",
        "dependencies": {
            "database": True,
            "cache": True,
        },
    }


@pytest.mark.django_db
def test_readiness_returns_503_when_database_is_unavailable(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "apps.core.views.dependency_health", lambda: {"database": False, "cache": True}
    )
    response = api_client.get(
        reverse("core:health-ready"),
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data == {
        "status": "unavailable",
        "dependencies": {
            "database": False,
            "cache": True,
        },
    }


@pytest.mark.django_db
def test_readiness_returns_503_when_cache_is_unavailable(
    api_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.core.views.dependency_health",
        lambda: {
            "database": True,
            "cache": False,
        },
    )

    response = api_client.get(
        reverse("core:health-ready"),
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data == {
        "status": "unavailable",
        "dependencies": {
            "database": True,
            "cache": False,
        },
    }
