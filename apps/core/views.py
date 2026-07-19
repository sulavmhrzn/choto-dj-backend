import structlog
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.health import dependency_health

logger = structlog.getLogger()


class LivenessAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request: Request) -> Response:
        return Response(data={"status": "ok"}, status=status.HTTP_200_OK)


class ReadinessAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request: Request) -> Response:
        dependencies = dependency_health()
        is_ready = all(dependencies.values())

        if not is_ready:
            logger.warning("application_not_ready", dependencies=dependencies)

        return Response(
            data={
                "status": "ok" if is_ready else "unavailable",
                "dependencies": dependencies,
            },
            status=(
                status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )
