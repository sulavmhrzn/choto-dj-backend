import secrets

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.constants import API_KEY_AUTH_SCHEME, API_KEY_VALUE_PREFIX
from apps.accounts.models import APIKey, User
from apps.accounts.selectors import api_key_get_active_by_prefix
from apps.accounts.services import api_key_mark_used, hash_api_key_secret
from apps.accounts.types import ParsedAPIKey


def parse_api_key_credential(*, credentials: str) -> ParsedAPIKey | None:
    if not credentials.startswith(API_KEY_VALUE_PREFIX):  # choto_prefix.secret
        return None

    value = credentials.removeprefix(API_KEY_VALUE_PREFIX)  # prefix.secret

    try:
        prefix, secret = value.split(".", maxsplit=1)  # prefix, secret
    except ValueError:
        return None

    if not prefix or not secret:
        return None

    return ParsedAPIKey(prefix=prefix, secret=secret)


class APIKeyAuthentication(BaseAuthentication):
    keyword = API_KEY_AUTH_SCHEME

    def authenticate(self, request: Request) -> tuple[User, APIKey] | None:
        authorization_header = get_authorization_header(
            request
        ).split()  # [Authorization, API-Key choto_prefix.secret]

        if not authorization_header:
            return None

        if authorization_header[0].decode().lower() != self.keyword.lower():  # api-key
            return None

        if len(authorization_header) != 2:
            raise AuthenticationFailed("Invalid API Key authorization header.")

        try:
            credential = authorization_header[1].decode()  # choto_prefix.secret
        except UnicodeError as exc:
            raise AuthenticationFailed("Invalid API Key authorization header.") from exc

        parsed_api_key = parse_api_key_credential(credentials=credential)

        if parsed_api_key is None:
            raise AuthenticationFailed("Invalid API Key.")

        api_key = api_key_get_active_by_prefix(prefix=parsed_api_key.prefix)

        if api_key is None:
            raise AuthenticationFailed("Invalid API Key.")

        supplied_hash = hash_api_key_secret(secret=parsed_api_key.secret)

        if not secrets.compare_digest(supplied_hash, api_key.hashed_secret):
            raise AuthenticationFailed("Invalid API Key.")

        api_key_mark_used(api_key=api_key)

        return api_key.owner, api_key

    def authenticate_header(self, request) -> str:
        return self.keyword


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = APIKeyAuthentication
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": f"{API_KEY_AUTH_SCHEME} <prefix>.<secret>",
        }
