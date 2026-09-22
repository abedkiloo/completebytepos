"""Resolve whether a sale was recorded from the web POS or the mobile app."""

from __future__ import annotations

VALID_CHANNELS = ('web', 'mobile', 'unknown')
ALIASES = {
    'app': 'mobile',
    'android': 'mobile',
    'ios': 'mobile',
    'flutter': 'mobile',
    'dart': 'mobile',
    'desktop': 'web',
    'browser': 'web',
    'spa': 'web',
}


def normalize_client_channel(value) -> str:
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    raw = ALIASES.get(raw, raw)
    if raw in VALID_CHANNELS:
        return raw
    return ''


def infer_client_channel_from_request(request) -> str:
    if request is None:
        return 'unknown'

    header = ''
    headers = getattr(request, 'headers', None)
    if headers is not None:
        header = headers.get('X-Client-Channel') or headers.get('x-client-channel') or ''
    if not header:
        meta = getattr(request, 'META', {}) or {}
        header = meta.get('HTTP_X_CLIENT_CHANNEL', '') or ''

    from_header = normalize_client_channel(header)
    if from_header in ('web', 'mobile'):
        return from_header

    ua = ''
    if headers is not None:
        ua = headers.get('User-Agent') or ''
    if not ua:
        ua = (getattr(request, 'META', {}) or {}).get('HTTP_USER_AGENT', '') or ''
    ua = ua.lower()
    if 'dart/' in ua or 'okhttp' in ua or 'flutter' in ua:
        return 'mobile'
    if ua:
        return 'web'
    return 'unknown'


def resolve_client_channel(request=None, payload=None) -> str:
    """Prefer an explicit payload, then X-Client-Channel, then User-Agent."""
    payload = payload or {}
    from_payload = normalize_client_channel(payload.get('client_channel'))
    if from_payload in ('web', 'mobile'):
        return from_payload
    inferred = infer_client_channel_from_request(request)
    if inferred in ('web', 'mobile'):
        return inferred
    return from_payload or inferred or 'unknown'
