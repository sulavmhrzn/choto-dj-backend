from apps.links.constants import RESERVED_SHORT_CODES


def is_reserved_short_code(*, short_code: str) -> bool:
    return short_code.lower() in RESERVED_SHORT_CODES
