"""RFC 8785 serialization for Core §8.3 dispositions.

Portable dispositions contain strings, arrays, objects, and (with RFC 0016)
Booleans. This small serializer implements only that closed value domain,
avoiding a dependency and RFC 8785's number-serialization surface entirely.
"""

from __future__ import annotations

from typing import Any


def canonicalize_disposition(disposition: dict[str, Any]) -> bytes:
    """Return the disposition's RFC 8785 (JCS) UTF-8 bytes."""

    if not isinstance(disposition, dict):
        raise TypeError("a disposition must be an object")
    return _serialize(disposition).encode("utf-8")


def _serialize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical object member names must be strings")
        members = sorted(value, key=_utf16_sort_key)
        return "{" + ",".join(
            _quote(key) + ":" + _serialize(value[key]) for key in members
        ) + "}"
    raise TypeError(
        "portable dispositions may contain only strings, Booleans, arrays, and objects"
    )


def _utf16_sort_key(value: str) -> bytes:
    _reject_lone_surrogates(value)
    # RFC 8785 follows ECMAScript/UTF-16 member-name ordering.
    return value.encode("utf-16-be")


def _quote(value: str) -> str:
    _reject_lone_surrogates(value)
    escapes = {
        '"': '\\"',
        "\\": "\\\\",
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
    }
    pieces = ['"']
    for character in value:
        escaped = escapes.get(character)
        if escaped is not None:
            pieces.append(escaped)
        elif ord(character) <= 0x1F:
            pieces.append(f"\\u{ord(character):04x}")
        else:
            pieces.append(character)
    pieces.append('"')
    return "".join(pieces)


def _reject_lone_surrogates(value: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("RFC 8785 does not admit lone Unicode surrogates")
