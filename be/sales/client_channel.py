"""Resolve whether a sale was recorded from the web POS or the mobile app."""

from utils.client_channel import (  # noqa: F401 — re-export for callers
    VALID_CHANNELS,
    ALIASES,
    normalize_client_channel,
    infer_client_channel_from_request,
    resolve_client_channel,
)
