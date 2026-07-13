import pytest

from apps.links.serializers import ShortLinkCreateSerializer


@pytest.mark.parametrize("short_code", ["my-link", "portoflio_2026", "abc123"])
def test_short_link_create_serializer_accepts_valid_custom_alias(short_code):
    serializer = ShortLinkCreateSerializer(
        data={"destination_url": "https://example.com", "short_code": short_code}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["short_code"] == short_code.lower()


def test_short_link_create_serializer_normalizes_alias_to_lowercase():
    serializer = ShortLinkCreateSerializer(
        data={"destination_url": "https://example.com", "short_code": "My-Portfolio"}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["short_code"] == "my-portfolio"


@pytest.mark.parametrize(
    "short_code",
    [
        "my link",
        "my/link",
        "my.link",
        "hello@world",
    ],
)
def test_short_link_create_serializer_rejects_invalid_alias_characters(
    short_code,
):
    serializer = ShortLinkCreateSerializer(
        data={
            "destination_url": "https://example.com",
            "short_code": short_code,
        }
    )

    assert serializer.is_valid() is False
    assert "short_code" in serializer.errors


@pytest.mark.parametrize(
    "short_code",
    [
        "admin",
        "API",
        "Login",
        "swagger",
    ],
)
def test_short_link_create_serializer_rejects_reserved_alias(
    short_code,
):
    serializer = ShortLinkCreateSerializer(
        data={
            "destination_url": "https://example.com",
            "short_code": short_code,
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors["short_code"][0] == ("This custom alias is reserved.")


def test_short_link_create_serializer_allows_missing_custom_alias():
    serializer = ShortLinkCreateSerializer(
        data={
            "destination_url": "https://example.com",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert "short_code" not in serializer.validated_data
