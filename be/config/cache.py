"""
Cache backend selection from environment.

Public entry points:
    - ``build_caches`` — **LocMem by default** (current production path).

Redis is deferred: leave ``REDIS_URL`` unset. When Redis is adopted later,
set ``REDIS_URL`` and install the ``redis`` package so multi-worker throttle
counters share one store. Until then prefer one Gunicorn worker with threads
so LocMem stays coherent inside a single process.
"""
from __future__ import annotations

import os
from typing import Any


def _env(name: str, default: str = '') -> str:
    return (os.getenv(name, default) or '').strip()


def build_caches(*, running_tests: bool = False) -> dict[str, Any]:
    """
    Build Django ``CACHES`` for this process.

    Args:
        running_tests: When True, always use LocMem so CI/tests need no Redis.

    Returns:
        A ``CACHES`` dict with a ``default`` alias. TIMEOUT is 30–300 seconds
        (from ``CACHE_TIMEOUT``, default 30). Redis uses ``django.core.cache``
        Redis backend when ``REDIS_URL`` is set and tests are not running.

    Raises:
        None. Invalid timeout falls back to 30.
    """
    raw_timeout = _env('CACHE_TIMEOUT', '30')
    try:
        timeout = int(raw_timeout)
    except ValueError:
        timeout = 30
    if timeout < 5:
        timeout = 5
    if timeout > 300:
        timeout = 300

    redis_url = _env('REDIS_URL')
    if redis_url and not running_tests:
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': redis_url,
                'TIMEOUT': timeout,
                'KEY_PREFIX': _env('CACHE_KEY_PREFIX', 'cbpos')[:40] or 'cbpos',
            }
        }

    return {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'completebytepos-settings',
            'TIMEOUT': timeout,
        }
    }
