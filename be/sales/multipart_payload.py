"""Normalize multipart sale payloads so ListField sees a real list of dicts.

Mobile POS sends cart ``items`` as a JSON string next to the receipt image.
Django ``QueryDict.__setitem__`` wraps assigned values, so putting the parsed
list back onto the QueryDict makes DRF ``ListField`` (via ``getlist``) see
``[[{...}]]`` and fail with::

    Expected a dictionary of items but got type "list".

Always coerce to a plain ``dict`` before validation.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping

from rest_framework.exceptions import ValidationError


def coerce_request_mapping(data: Any) -> dict[str, Any]:
    """Return a plain dict from QueryDict / mapping request data.

    Args:
        data: DRF ``request.data``, a ``QueryDict``, mapping, or None.
            Empty / None yields ``{}``. Multi-value QueryDict keys keep the
            last value (same as ``QueryDict.items()``).

    Returns:
        A new ``dict`` suitable for serializer ``to_internal_value``. Never
        returns a ``QueryDict``.
    """
    if data is None:
        return {}
    # Plain dict (not QueryDict): copy so callers can mutate safely.
    if isinstance(data, dict) and not hasattr(data, 'getlist'):
        return dict(data)
    if isinstance(data, Mapping):
        return {key: value for key, value in data.items()}
    if hasattr(data, 'items'):
        return {key: value for key, value in data.items()}
    return {}


def parse_json_items_field(
    data: Any,
    *,
    field: str = 'items',
) -> dict[str, Any]:
    """Parse a JSON-encoded ``items`` list from multipart form fields.

    Args:
        data: Incoming request mapping (0+ keys). ``field`` may be a JSON
            string of 0–500 cart lines, an already-parsed ``list`` of dicts,
            or missing.
        field: Form key to parse; 1–64 chars. Defaults to ``items``.

    Returns:
        Plain dict with ``field`` as a ``list`` when it was a JSON string.
        Other keys are unchanged (last value per key).

    Raises:
        ValidationError: When ``field`` is a non-JSON string, or JSON that is
            not a list (mobile always sends a list of line dicts).
    """
    mutable: MutableMapping[str, Any] = coerce_request_mapping(data)
    raw = mutable.get(field)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError({field: 'Invalid items payload.'}) from exc
        if not isinstance(parsed, list):
            raise ValidationError(
                {field: 'Items must be a JSON list of line objects.'}
            )
        mutable[field] = parsed
    elif (
        isinstance(raw, list)
        and len(raw) == 1
        and isinstance(raw[0], list)
    ):
        # Defensive unwrap if a caller already assigned onto a QueryDict.
        mutable[field] = raw[0]
    return dict(mutable)
