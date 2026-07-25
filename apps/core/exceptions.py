from rest_framework import status
from rest_framework.exceptions import APIException


class IdempotencyConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = ["Idempotency Key was already used with a different request."]
    default_code = "idempotency_conflict"
