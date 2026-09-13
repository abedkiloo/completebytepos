"""
Read typed configuration from environment variables (.env).
"""
from __future__ import annotations

import os
from pathlib import Path


def env_str(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def env_list(name: str, default: list[str] | None = None, sep: str = ',') -> list[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        return list(default or [])
    if raw.strip() == '*':
        return ['*']
    items = [
        part.strip().strip('"').strip("'")
        for part in raw.split(sep)
        if part.strip()
    ]
    return items


def merge_unique_list(*lists: list[str] | None) -> list[str]:
    """Merge lists preserving order, dropping empty duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        if not lst:
            continue
        for item in lst:
            key = (item or '').strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out


def env_path(name: str, default: Path | str) -> Path:
    raw = env_str(name)
    if raw:
        return Path(raw)
    return Path(default)


def env_csv_or_lines(name: str, default: list[str] | None = None) -> list[str]:
    """Comma-separated list, or newline-separated if value contains \\n."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default or [])
    if '\n' in raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return env_list(name, default)


def normalize_public_host(raw: str) -> str:
    """Strip scheme/path from PUBLIC_HOST so ALLOWED_HOSTS gets a bare hostname."""
    host = (raw or '').strip()
    if not host:
        return ''
    for prefix in ('https://', 'http://'):
        if host.lower().startswith(prefix):
            host = host[len(prefix) :]
            break
    host = host.split('/')[0].strip()
    return host.rstrip('.')


def is_ip_like_host(host: str) -> bool:
    """True for IPv4 (optional :port). Domains and IPv6 netlocs return False."""
    bare = (host or '').strip().split('%')[0]
    if bare.startswith('[') and ']' in bare:
        return True  # [IPv6]
    hostname = bare.split(':')[0]
    parts = hostname.split('.')
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def public_host_origins(host: str) -> list[str]:
    """
    http + https origins for CSRF/CORS from PUBLIC_HOST.

    Includes :3000/:8000 for IP/dev access; bare https://domain for reverse-proxy TLS.
    """
    host = normalize_public_host(host)
    if not host:
        return []
    origins = [
        f'http://{host}',
        f'https://{host}',
    ]
    # Host already has an explicit port (e.g. 193.x.x.x:3000)
    if ':' in host and not host.startswith('['):
        return origins
    origins.extend(
        [
            f'http://{host}:3000',
            f'http://{host}:8000',
            f'https://{host}:3000',
            f'https://{host}:8000',
        ]
    )
    return origins
