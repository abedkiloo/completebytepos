"""
Read typed configuration from environment variables (.env).

Public entry points:
    - ``env_str`` / ``env_bool`` / ``env_int`` / ``env_list`` / ``env_path``
    - ``env_csv_or_lines`` — comma or newline separated lists
    - ``normalize_public_host`` / ``public_host_origins`` — CSRF/CORS host helpers

Missing vars fall back to defaults; invalid ints fall back without raising.
"""
from __future__ import annotations

import os
from pathlib import Path


def env_str(name: str, default: str = '') -> str:
    """
    Read a stripped string environment variable.

    Args:
        name: Variable name.
        default: Value when unset (also stripped).

    Returns:
        Non-None string (may be empty).
    """
    return os.getenv(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    """
    Parse a truthy environment flag.

    Args:
        name: Variable name.
        default: Used when the variable is unset.

    Returns:
        ``True`` for ``1``, ``true``, ``yes``, ``on`` (case-insensitive); else ``False``.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def env_int(name: str, default: int) -> int:
    """
    Parse an integer environment variable.

    Args:
        name: Variable name.
        default: Returned when unset, blank, or non-numeric.

    Returns:
        Parsed int or ``default``.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def env_list(name: str, default: list[str] | None = None, sep: str = ',') -> list[str]:
    """
    Split a delimited environment list.

    Args:
        name: Variable name.
        default: Used when unset or blank (copied to a new list).
        sep: Delimiter (default comma).

    Returns:
        List of stripped tokens; literal ``*`` alone returns ``['*']``.
    """
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
    """
    Merge string lists preserving first-seen order.

    Args:
        *lists: Optional lists; ``None`` and empty lists are skipped.

    Returns:
        De-duplicated list; strips whitespace; drops blank entries.
    """
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
    """
    Resolve a filesystem path from the environment.

    Args:
        name: Variable name.
        default: Used when the variable is empty after strip.

    Returns:
        ``Path`` instance.
    """
    raw = env_str(name)
    if raw:
        return Path(raw)
    return Path(default)


def env_csv_or_lines(name: str, default: list[str] | None = None) -> list[str]:
    """
    Parse comma-separated or newline-separated env lists.

    Args:
        name: Variable name.
        default: When unset or blank.

    Returns:
        Non-empty lines when ``\\n`` present; otherwise ``env_list`` result.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default or [])
    if '\n' in raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return env_list(name, default)


def normalize_public_host(raw: str) -> str:
    """
    Strip scheme and path from a public host string.

    Args:
        raw: Host or URL (``https://shop.example.com/path``).

    Returns:
        Bare hostname without trailing dot; empty when input blank.
    """
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
    """
    Detect IPv4 literals (optional ``:port``) for dev origin rules.

    Args:
        host: Host header or origin host.

    Returns:
        ``True`` for dotted IPv4 or bracketed IPv6 netloc; ``False`` for domains.
    """
    bare = (host or '').strip().split('%')[0]
    if bare.startswith('[') and ']' in bare:
        return True  # [IPv6]
    hostname = bare.split(':')[0]
    parts = hostname.split('.')
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def public_host_origins(host: str) -> list[str]:
    """
    Build http/https origins for CSRF/CORS from ``PUBLIC_HOST``.

    Args:
        host: Raw host string (normalized internally).

    Returns:
        ``http``/``https`` origins; adds ``:3000`` and ``:8000`` variants when the
        host has no explicit port (skipped for hosts that already include ``:port``).
        Empty list when host normalizes to blank.
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
