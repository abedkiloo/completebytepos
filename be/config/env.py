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
    items = [part.strip() for part in raw.split(sep) if part.strip()]
    return items


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
