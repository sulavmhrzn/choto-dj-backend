from typing import Any

from rest_framework.renderers import JSONRenderer


class StructuredJSONRenderer(JSONRenderer):
    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: dict[str, Any] | None = None,
    ):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")

        if response is None:
            return super().render(
                data,
                accepted_media_type,
                renderer_context,
            )

        if response.status_code >= 400:
            return super().render(
                data,
                accepted_media_type,
                renderer_context,
            )

        if response.status_code == 204:
            return b""

        structured_data = {
            "success": True,
            "message": self._get_message(data),
            "data": self._get_data(data),
            "errors": None,
        }
        return super().render(
            structured_data,
            accepted_media_type,
            renderer_context,
        )

    @staticmethod
    def _get_message(data: Any) -> str:
        if isinstance(data, dict):
            message = data.get("custom_message")
            if isinstance(message, str):
                return message

        return "Request completed successfully."

    @staticmethod
    def _get_data(data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        response_data = data.copy()
        response_data.pop("custom_message", None)
        return response_data or None
