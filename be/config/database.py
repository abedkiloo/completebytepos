"""
Database configuration from environment variables (.env).

PostgreSQL is the default. Set USE_SQLITE=true only for legacy/local fallback.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse


def _env(name: str, default: str = '') -> str:
    return os.getenv(name, default)


def _postgres_from_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ('postgres', 'postgresql'):
        raise ValueError(f'Unsupported DATABASE_URL scheme: {parsed.scheme}')
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': (parsed.path or '/completebytepos').lstrip('/'),
        'USER': unquote(parsed.username or 'completebytepos'),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname or 'localhost',
        'PORT': str(parsed.port or 5432),
    }


def build_databases(*, base_dir: Path, running_tests: bool = False) -> dict:
    database_url = _env('DATABASE_URL')
    # For quick local test verification prefer SQLite when running the test suite.
    use_sqlite = running_tests or _env('USE_SQLITE', 'false').lower() in ('1', 'true', 'yes')

    if database_url and not use_sqlite:
        cfg = _postgres_from_url(database_url)
    elif use_sqlite:
        db_path = _env('DB_PATH') or str(base_dir / 'db.sqlite3')
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': db_path,
            }
        }
    else:
        name = _env('POSTGRES_DB', _env('DB_NAME', 'completebytepos'))
        if running_tests and _env('TEST_POSTGRES_DB'):
            name = _env('TEST_POSTGRES_DB')
        cfg = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': name,
            'USER': _env('POSTGRES_USER', _env('DB_USER', 'completebytepos')),
            'PASSWORD': _env('POSTGRES_PASSWORD', _env('DB_PASSWORD', 'completebytepos')),
            'HOST': _env('DB_HOST', 'localhost'),
            'PORT': _env('DB_PORT', _env('POSTGRES_PORT', '5432')),
        }

    conn_max_age = _env('DB_CONN_MAX_AGE', '60')
    return {
        'default': {
            **cfg,
            'CONN_MAX_AGE': int(conn_max_age) if conn_max_age.isdigit() else 60,
            'OPTIONS': {},
        }
    }


def is_postgresql_config(databases: dict) -> bool:
    engine = databases.get('default', {}).get('ENGINE', '')
    return 'postgresql' in engine


def reset_default_database() -> None:
    """Drop all tables — used by fresh-install (PostgreSQL or SQLite file)."""
    from django.conf import settings
    from django.db import connection

    if is_postgresql_config(settings.DATABASES):
        db_user = settings.DATABASES['default']['USER']
        with connection.cursor() as cursor:
            cursor.execute('DROP SCHEMA public CASCADE;')
            cursor.execute('CREATE SCHEMA public;')
            cursor.execute('GRANT ALL ON SCHEMA public TO public;')
            cursor.execute(f'GRANT ALL ON SCHEMA public TO "{db_user}";')
    else:
        db_name = settings.DATABASES['default']['NAME']
        path = Path(db_name)
        if path.exists():
            path.unlink()
