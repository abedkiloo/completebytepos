"""
Django settings for CompleteBytePOS project.
All deployment-specific values come from environment variables — see .env.example.
"""
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from config.database import build_databases
from config.env import env_bool, env_csv_or_lines, env_int, env_list, env_path, env_str, merge_unique_list

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env: workspace root (be+fe layout) overrides be/.env
load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env', override=True)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env_str(
    'SECRET_KEY',
    'django-insecure-change-me-before-production',
)
DEBUG = env_bool('DEBUG', True)

# Docker nginx proxies with Host: backend — always keep internal names allowed.
_DOCKER_ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'backend', 'frontend']
PUBLIC_HOST = env_str('PUBLIC_HOST') or env_str('SERVER_IP') or env_str('SERVER_PUBLIC_IP')
ALLOWED_HOSTS = merge_unique_list(
    env_list('ALLOWED_HOSTS', _DOCKER_ALLOWED_HOSTS),
    _DOCKER_ALLOWED_HOSTS,
    [PUBLIC_HOST] if PUBLIC_HOST else [],
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'products',
    'sales',
    'inventory',
    'accounts',
    'reports',
    'barcodes',
    'expenses',
    'accounting',
    'income',
    'bankaccounts',
    'transfers',
    'suppliers',
    'employees',
    'daily_notes',
    'settings',
    'approvals',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

try:
    import whitenoise  # noqa: F401

    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
RUNNING_TESTS = 'test' in sys.argv
DATABASES = build_databases(base_dir=BASE_DIR, running_tests=RUNNING_TESTS)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'completebytepos-settings',
        'TIMEOUT': 30,
    },
}

# ---------------------------------------------------------------------------
# Auth / i18n
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = env_str('LANGUAGE_CODE', 'en-us')
TIME_ZONE = env_str('TIME_ZONE', 'Africa/Nairobi')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = env_str('STATIC_URL', '/static/')
STATIC_ROOT = env_path('STATIC_ROOT', BASE_DIR / 'staticfiles')

try:
    import whitenoise  # noqa: F401

    STATICFILES_STORAGE = env_str(
        'STATICFILES_STORAGE',
        'whitenoise.storage.CompressedManifestStaticFilesStorage',
    )
except ImportError:
    pass

MEDIA_URL = env_str('MEDIA_URL', '/media/')
# Avoid Docker /app paths during manage.py test (local .env often sets MEDIA_ROOT=/app/media).
if 'test' in sys.argv:
    MEDIA_ROOT = BASE_DIR / 'test_media'
else:
    MEDIA_ROOT = env_path('MEDIA_ROOT', BASE_DIR / 'media')
# Serve uploads from Django/gunicorn when not using S3 (required when DEBUG=False).
SERVE_MEDIA = env_bool('SERVE_MEDIA', True)
# Browser-facing base for image_url (nginx on FRONTEND_PORT proxies /media/ → backend).
MEDIA_PUBLIC_BASE_URL = env_str('MEDIA_PUBLIC_BASE_URL')
MEDIA_PUBLIC_PORT = env_int('MEDIA_PUBLIC_PORT', 0) or None
# In DEBUG, CRA serves the app on :3000 without /media unless setupProxy is used;
# prefer relative /media/ URLs from the API (absolute base is set in production).
if not MEDIA_PUBLIC_BASE_URL and PUBLIC_HOST and not DEBUG:
    _fe_port = env_str('FRONTEND_PORT', '3000')
    MEDIA_PUBLIC_BASE_URL = f'http://{PUBLIC_HOST}:{_fe_port}'
    if MEDIA_PUBLIC_PORT is None:
        try:
            MEDIA_PUBLIC_PORT = int(_fe_port)
        except ValueError:
            MEDIA_PUBLIC_PORT = 3000

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# REST / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': env_int('API_PAGE_SIZE', 10),
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
    'URL_FORMAT_OVERRIDE': None,
    'FORMAT_SUFFIX_KWARG': None,
    'DEFAULT_THROTTLE_RATES': {
        'login': env_str('THROTTLE_LOGIN_RATE', '10/min'),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env_int('JWT_ACCESS_TOKEN_MINUTES', 30)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env_int('JWT_REFRESH_TOKEN_DAYS', 7)),
    'ROTATE_REFRESH_TOKENS': env_bool('JWT_ROTATE_REFRESH_TOKENS', True),
    'BLACKLIST_AFTER_ROTATION': env_bool('JWT_BLACKLIST_AFTER_ROTATION', True),
    'UPDATE_LAST_LOGIN': env_bool('JWT_UPDATE_LAST_LOGIN', False),
    'ALGORITHM': env_str('JWT_ALGORITHM', 'HS256'),
    'SIGNING_KEY': env_str('JWT_SIGNING_KEY', SECRET_KEY),
    'AUTH_HEADER_TYPES': tuple(
        env_list('JWT_AUTH_HEADER_TYPES', ['Bearer'])
    ),
    'AUTH_HEADER_NAME': env_str('JWT_AUTH_HEADER_NAME', 'HTTP_AUTHORIZATION'),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# ---------------------------------------------------------------------------
# Security (cookies / HTTPS)
# ---------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = merge_unique_list(
    env_csv_or_lines(
        'CSRF_TRUSTED_ORIGINS',
        [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:8000',
        ],
    ),
    [
        f'http://{PUBLIC_HOST}',
        f'http://{PUBLIC_HOST}:3000',
        f'http://{PUBLIC_HOST}:8000',
    ]
    if PUBLIC_HOST
    else [],
)
CSRF_COOKIE_HTTPONLY = env_bool('CSRF_COOKIE_HTTPONLY', False)
CSRF_COOKIE_SAMESITE = env_str('CSRF_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', False)

SESSION_COOKIE_HTTPONLY = env_bool('SESSION_COOKIE_HTTPONLY', True)
SESSION_COOKIE_SAMESITE = env_str('SESSION_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', False)

SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', False)
if env_bool('USE_SECURE_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', DEBUG)
CORS_ALLOW_CREDENTIALS = env_bool('CORS_ALLOW_CREDENTIALS', True)

_default_cors_origins = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://frontend:80',
    'http://frontend',
]
CORS_ALLOWED_ORIGINS = merge_unique_list(
    env_csv_or_lines('CORS_ALLOWED_ORIGINS', _default_cors_origins),
    [
        f'http://{PUBLIC_HOST}',
        f'http://{PUBLIC_HOST}:3000',
        f'http://{PUBLIC_HOST}:8000',
    ]
    if PUBLIC_HOST
    else [],
)

_extra_cors_headers = env_csv_or_lines(
    'CORS_EXTRA_ALLOWED_HEADERS',
    ['x-branch-id', 'X-Branch-ID', 'ngrok-skip-browser-warning'],
)
try:
    from corsheaders.defaults import default_headers

    CORS_ALLOWED_HEADERS = list(default_headers) + _extra_cors_headers
except ImportError:
    CORS_ALLOWED_HEADERS = [
        'accept',
        'accept-encoding',
        'authorization',
        'content-type',
        'origin',
        'user-agent',
        'x-csrftoken',
        'x-requested-with',
        *_extra_cors_headers,
    ]

CORS_ALLOW_METHODS = env_csv_or_lines(
    'CORS_ALLOW_METHODS',
    ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT'],
)

_cors_regex_default = [
    r'^https://.*\.ngrok-free\.app$',
    r'^https://.*\.ngrok\.io$',
    r'^https://.*\.ngrok\.app$',
]
CORS_ALLOWED_ORIGIN_REGEXES = env_csv_or_lines(
    'CORS_ALLOWED_ORIGIN_REGEXES',
    _cors_regex_default,
)

CORS_EXPOSE_HEADERS = env_csv_or_lines(
    'CORS_EXPOSE_HEADERS',
    ['content-type', 'authorization'],
)
CORS_PREFLIGHT_MAX_AGE = env_int('CORS_PREFLIGHT_MAX_AGE', 86400)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = env_str('LOG_LEVEL', 'INFO')
DJANGO_LOG_LEVEL = env_str('DJANGO_LOG_LEVEL', LOG_LEVEL)
DJANGO_REQUEST_LOG_LEVEL = env_str('DJANGO_REQUEST_LOG_LEVEL', 'ERROR')

_LOG_HANDLERS = {
    'console': {
        'level': LOG_LEVEL,
        'class': 'logging.StreamHandler',
        'formatter': 'simple',
    },
}
if not RUNNING_TESTS:
    logs_dir = env_path('LOG_DIR', BASE_DIR / 'logs')
    logs_dir.mkdir(parents=True, exist_ok=True)
    _LOG_HANDLERS['file'] = {
        'level': env_str('LOG_FILE_LEVEL', 'ERROR'),
        'class': 'logging.FileHandler',
        'filename': logs_dir / 'error.log',
        'formatter': 'verbose',
    }
    _LOG_HANDLERS['api_file'] = {
        'level': env_str('LOG_API_FILE_LEVEL', 'INFO'),
        'class': 'logging.FileHandler',
        'filename': logs_dir / 'api.log',
        'formatter': 'verbose',
    }

_FILE_HANDLERS = ['file'] if 'file' in _LOG_HANDLERS else ['console']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} [{module}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': _LOG_HANDLERS,
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': DJANGO_LOG_LEVEL,
            'propagate': False,
        },
        'django.request': {
            'handlers': _FILE_HANDLERS,
            'level': DJANGO_REQUEST_LOG_LEVEL,
            'propagate': False,
        },
        'settings': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'sales': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'inventory': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'barcodes': {'handlers': _FILE_HANDLERS, 'level': 'ERROR', 'propagate': False},
        'config': {'handlers': _FILE_HANDLERS, 'level': 'ERROR', 'propagate': False},
        'corsheaders': {
            'handlers': ['console'],
            'level': env_str('CORS_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console', *_FILE_HANDLERS],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}
