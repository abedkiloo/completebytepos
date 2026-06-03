"""Build browser-reachable URLs for uploaded media (product images, etc.)."""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from django.conf import settings


def _normalize_path(url: str) -> str:
    if not url:
        return ''
    return url if url.startswith('/') else f'/{url}'


def _fix_internal_hostname(absolute_url: str) -> str:
    """Replace docker-internal hostnames with the public site host."""
    parsed = urlparse(absolute_url)
    if parsed.hostname not in ('backend', 'frontend', '0.0.0.0'):
        return absolute_url

    public = (getattr(settings, 'PUBLIC_HOST', None) or '').strip()
    if not public:
        return absolute_url

    port = parsed.port
    base_port = getattr(settings, 'MEDIA_PUBLIC_PORT', None)
    if base_port:
        try:
            port = int(str(base_port).strip())
        except ValueError:
            port = parsed.port
    elif getattr(settings, 'MEDIA_PUBLIC_BASE_URL', ''):
        base_parsed = urlparse(settings.MEDIA_PUBLIC_BASE_URL.strip())
        port = base_parsed.port

    netloc = f'{public}:{port}' if port else public
    return urlunparse(parsed._replace(netloc=netloc))


def absolute_media_url(request, relative_url: str | None) -> str | None:
    """
    Return an absolute URL for a FileField/ImageField `.url` value.

    Prefer MEDIA_PUBLIC_BASE_URL (e.g. http://your-vps:3000) so images load via nginx.
    """
    if not relative_url:
        return None

    path = _normalize_path(relative_url)
    base = (getattr(settings, 'MEDIA_PUBLIC_BASE_URL', None) or '').strip().rstrip('/')
    if base:
        return f'{base}{path}'

    if request is not None:
        return _fix_internal_hostname(request.build_absolute_uri(path))

    public = (getattr(settings, 'PUBLIC_HOST', None) or '').strip()
    if public:
        port = getattr(settings, 'MEDIA_PUBLIC_PORT', None)
        host = f'{public}:{port}' if port else public
        return f'http://{host}{path}'

    return path
