import pytest

from apps.accounts.models import User
from apps.links.services import short_link_create


@pytest.fixture
def user():
    return User.objects.create_user(email="sulav@mail.com", password="strong-password")


@pytest.mark.django_db
def test_short_link_create_rejects_duplicate_custom_alias(user):
    short_link_create(
        owner=user,
        destination_url="https://example.com/first",
        short_code="portfolio",
    )

    with pytest.raises(
        ValueError,
        match="This custom alias is already in use.",
    ):
        short_link_create(
            owner=user,
            destination_url="https://example.com/second",
            short_code="portfolio",
        )
