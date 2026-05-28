"""
Django settings for CompleteBytePOS project.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# NOTE: A previous version of this file monkey-patched Django's MigrationLoader
# and MigrationGraph to silently swallow NodeNotFoundError /
# InconsistentMigrationHistory for built-in apps (auth, contenttypes, sessions,
# admin). The real cause was a corrupted local virtualenv where some of those
# built-in migration files had been deleted from site-packages, NOT a Django
# bug. The patch only hid the corruption and made `makemigrations` crash
# elsewhere with a confusing `AttributeError` inside `make_state`.
# The fix is to keep the venv intact (e.g. `pip install --force-reinstall
# --no-deps Django==4.2.27 djangorestframework-simplejwt==5.5.1`) and let
# Django's own migration machinery enforce consistency. If migrations ever look
# wrong again, fix the cause, do not paper over it.

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-sps$ltgla=lnb4a44o)2v)e3(42in*@43io^d8b*%$byycxf78')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '*']  # Allow all hosts for now

# Application definition
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
    'employees',  # Employee Management
    'settings',  # Settings app for module settings and future system settings
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'middleware.cors_logging.CORSLoggingMiddleware',  # Log CORS requests
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Add WhiteNoise middleware if available (for production)
try:
    import whitenoise
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass  # WhiteNoise not installed, skip it

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

# Database
# SQLite Configuration (can switch to MySQL/PostgreSQL later)
# Database configuration
# Support Docker volume mount for database
DB_PATH = os.environ.get('DB_PATH', None)
if DB_PATH:
    # Docker environment - use provided path
    DATABASE_NAME = DB_PATH
else:
    # Local development - use project directory
    DATABASE_NAME = BASE_DIR / 'db.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(DATABASE_NAME),
    }
}

# For MySQL (future use):
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': os.getenv('DB_NAME', 'completebytepos'),
#         'USER': os.getenv('DB_USER', 'root'),
#         'PASSWORD': os.getenv('DB_PASSWORD', ''),
#         'HOST': os.getenv('DB_HOST', 'localhost'),
#         'PORT': os.getenv('DB_PORT', '3306'),
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#             'charset': 'utf8mb4',
#         },
#     }
# }
# import pymysql
# pymysql.install_as_MySQLdb()

# For PostgreSQL (future use):
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME', 'completebytepos'),
#         'USER': os.getenv('DB_USER', 'postgres'),
#         'PASSWORD': os.getenv('DB_PASSWORD', ''),
#         'HOST': os.getenv('DB_HOST', 'localhost'),
#         'PORT': os.getenv('DB_PORT', '5432'),
#     }
# }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'  # Kenya timezone
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise configuration for serving static files in production (if available)
try:
    import whitenoise
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
except ImportError:
    pass  # WhiteNoise not installed, use default storage

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Custom pagination class that honours ``?page_size=N`` (capped at
    # ``max_page_size``). Backward-compatible: existing clients that don't
    # supply page_size still get the default 20.
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
    'URL_FORMAT_OVERRIDE': None,  # Disable format suffix in URL to prevent conflicts with query params
    'FORMAT_SUFFIX_KWARG': None,  # Disable format suffix handling completely
    # Throttling: opt-in per-view via throttle_classes + throttle_scope.
    # We don't set DEFAULT_THROTTLE_CLASSES because most endpoints don't
    # benefit from rate limiting and would just add overhead.
    'DEFAULT_THROTTLE_RATES': {
        # Login endpoint (AuthViewSet.login uses ScopedRateThrottle with
        # throttle_scope='login'). 10 attempts per minute per IP is enough
        # for honest typo recovery; brute-force needs 1000s/min to succeed.
        'login': '10/min',
    },
}

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),  # Token expires after 1 hour
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,  # Set to False to avoid requiring last_login field
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CSRF settings for API - Allow all origins for now
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://216.158.230.163:3000',  # Server frontend
    'http://216.158.230.163:8000',  # Server backend
 
]
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to read CSRF token
CSRF_COOKIE_SAMESITE = 'Lax'
# Disable CSRF for API endpoints (using JWT instead)
CSRF_COOKIE_SECURE = False  # Set to True in production with HTTPS

# CORS settings - Allow all origins for now
# In Docker, nginx proxy handles CORS, but we keep this for direct API access
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Docker network origins (if accessing backend directly)
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8000',
    'http://frontend:80',
    'http://frontend',
    'http://216.158.230.163:3000',
    'http://216.158.230.163:8000',
    'http://127.0.0.1:3000',  # Also allow 127.0.0.1
]

# Allow all headers (including preflight request headers)
# Use default headers from django-cors-headers and add our custom header
try:
    from corsheaders.defaults import default_headers
    CORS_ALLOWED_HEADERS = list(default_headers) + [
        'x-branch-id',  # Custom header for branch selection
        'X-Branch-ID',  # Also allow uppercase version (browsers may send either)
        'ngrok-skip-browser-warning',  # Allow ngrok header to bypass warning page
    ]
except ImportError:
    # Fallback if default_headers is not available
    CORS_ALLOWED_HEADERS = [
        'accept',
        'accept-encoding',
        'authorization',
        'content-type',
        'dnt',
        'origin',
        'user-agent',
        'x-csrftoken',
        'x-requested-with',
        'x-branch-id',  # Custom header for branch selection
        'X-Branch-ID',  # Also allow uppercase version
        'access-control-request-headers',
        'access-control-request-method',
        'sec-fetch-mode',
        'sec-fetch-site',
        'sec-fetch-dest',
        'ngrok-skip-browser-warning',  # Allow ngrok header to bypass warning page
    ]

# Ensure x-branch-id is always included (case-insensitive check)
if not any('branch-id' in h.lower() for h in CORS_ALLOWED_HEADERS):
    CORS_ALLOWED_HEADERS.extend(['x-branch-id', 'X-Branch-ID'])
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
# Allow ngrok and other tunneling services
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.ngrok-free\.app$",
    r"^https://.*\.ngrok\.io$",
    r"^https://.*\.ngrok\.app$",
]
# Expose headers for CORS
CORS_EXPOSE_HEADERS = [
    'content-type',
    'authorization',
]
# Preflight cache duration (in seconds)
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

# Session configuration
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Logging configuration - skip file handlers during ``manage.py test`` (sandbox-safe)
RUNNING_TESTS = 'test' in sys.argv

_LOG_HANDLERS = {
    'console': {
        'level': 'INFO',
        'class': 'logging.StreamHandler',
        'formatter': 'simple',
    },
}
if not RUNNING_TESTS:
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    _LOG_HANDLERS['file'] = {
        'level': 'ERROR',
        'class': 'logging.FileHandler',
        'filename': logs_dir / 'error.log',
        'formatter': 'verbose',
    }
    _LOG_HANDLERS['api_file'] = {
        'level': 'INFO',
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
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': _FILE_HANDLERS,
            'level': 'ERROR',
            'propagate': False,
        },
        'settings': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'sales': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'middleware.cors_logging': {
            'handlers': ['console'],
            'level': 'WARNING',  # Only log warnings/errors for CORS
            'propagate': False,
        },
        'barcodes': {
            'handlers': _FILE_HANDLERS,
            'level': 'ERROR',
            'propagate': False,
        },
        'config': {
            'handlers': _FILE_HANDLERS,
            'level': 'ERROR',
            'propagate': False,
        },
        'corsheaders': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console', *_FILE_HANDLERS],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
