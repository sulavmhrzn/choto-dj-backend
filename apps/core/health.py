from typing import TypedDict
from uuid import uuid4

from django.core.cache import cache
from django.db import connection


class DependencyHealth(TypedDict):
    database: bool
    cache: bool


def database_is_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return False
    return True


def cache_is_ready() -> bool:
    key = f"health-check:{uuid4()}"
    value = "ok"

    try:
        cache.set(key, value, timeout=10)
        cached_value = cache.get(key)
        cache.delete(key)
    except Exception:
        return False
    return cached_value == value


def dependency_health() -> DependencyHealth:
    return DependencyHealth(
        database=database_is_ready(),
        cache=cache_is_ready(),
    )
