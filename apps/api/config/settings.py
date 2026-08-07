"""Django settings for NakitPilot API."""

import os
import sys
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv

from config.env import env_bool, env_list, resolve_database_config

BASE_DIR = Path(__file__).resolve().parent.parent

# Load order: API local → repo root (later files do not override existing keys by default)
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent.parent / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Copy apps/api/.env.example to .env and fill secrets."
    )

JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY") or SECRET_KEY

DEBUG = env_bool("DEBUG", env_bool("DJANGO_DEBUG", True))

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"),
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    # NakitPilot
    "apps.accounts",
    "apps.organizations",
    "apps.customers",
    "apps.invoices",
    "apps.payments",
    "apps.collections",
    "apps.imports",
    "apps.integrations",
    "apps.api_keys",
    "apps.public_api",
    "apps.webhooks",
    "apps.developers",
    "apps.workflows",
    "apps.risk",
    "apps.forecasting",
    "apps.dashboard",
    "apps.messaging",
    "apps.ai_usage",
    "apps.notifications",
    "apps.audit",
    "apps.security",
    "apps.reports",
    "apps.health",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.organizations.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": resolve_database_config()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# NP-152: uploads live outside MEDIA_URL-served tree (never web-root).
PRIVATE_UPLOAD_ROOT = Path(
    os.getenv("PRIVATE_UPLOAD_ROOT", str(BASE_DIR / "private_uploads"))
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

# NP-151 — strict in production; relaxed when DEBUG so test suites aren't blocked.
_AUTH_LOGIN_RATE = os.getenv("AUTH_LOGIN_RATE") or ("1000/min" if DEBUG else "10/min")
_AUTH_REFRESH_RATE = os.getenv("AUTH_REFRESH_RATE") or ("1000/min" if DEBUG else "30/min")
_IMPORT_UPLOAD_RATE = os.getenv("IMPORT_UPLOAD_RATE") or ("1000/min" if DEBUG else "20/hour")
_PUBLIC_API_RATE = os.getenv("PUBLIC_API_RATE") or ("1000/min" if DEBUG else "60/min")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.api_keys.authentication.ApiKeyAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": _AUTH_LOGIN_RATE,
        "auth_refresh": _AUTH_REFRESH_RATE,
        "import_upload": _IMPORT_UPLOAD_RATE,
        "public_api": _PUBLIC_API_RATE,
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NakitPilot Public API",
    "DESCRIPTION": "Organization-scoped public REST API authenticated with API keys (NP-201).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"ApiKeyAuth": []}, {"BearerApiKey": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Api-Key",
                "description": "Organization API key (npk_…)",
            },
            "BearerApiKey": {
                "type": "http",
                "scheme": "bearer",
                "description": "Authorization: Bearer npk_…",
            },
        }
    },
}

# NP-154 — never log secrets / PII in clear text
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sensitive_data": {
            "()": "apps.security.masking.SensitiveDataFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["sensitive_data"],
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.EmailTokenObtainPairSerializer",
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost,http://127.0.0.1",
)

# Browser preflight must allow tenant header used by apiRequest (X-Organization-Id).
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-organization-id",
]

# ---------------------------------------------------------------------------
# Cache / Celery (Redis)
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# LocMem for pytest / explicit flag / local DEBUG without Redis.
# Production (DEBUG=false) uses Redis so rate limits are shared across workers.
_RUNNING_TESTS = env_bool("USE_LOCMEM_CACHE", False) or any(
    "pytest" in arg for arg in sys.argv
)

if _RUNNING_TESTS or (DEBUG and not env_bool("USE_REDIS_CACHE", False)):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "nakitpilot-local",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_CACHE_URL", REDIS_URL),
        }
    }

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
# NP-142: jobs run per organization timezone via dispatcher (not fixed UTC).
# Local times: 08:00 reminders, 00:15 overdue invoices, 00:30 broken promises,
# 01:00 risk, Monday 01:30 weekly forecast.

# ---------------------------------------------------------------------------
# Email (NP-240)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG or _RUNNING_TESTS
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@nakitpilot.local")
PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
CELERY_BEAT_SCHEDULE = {
    "dispatch-org-timezone-jobs": {
        "task": "notifications.dispatch_org_timezone_jobs",
        "schedule": crontab(minute="*/5"),
    },
    "expire-report-exports-hourly": {
        "task": "reports.expire_stale_exports",
        "schedule": crontab(minute=20),
    },
    "process-due-webhook-deliveries": {
        "task": "webhooks.process_due_deliveries",
        "schedule": crontab(minute="*/1"),
    },
    "process-due-workflow-resumes": {
        "task": "workflows.process_due_resumes",
        "schedule": crontab(minute="*/1"),
    },
}

# ---------------------------------------------------------------------------
# Object storage (S3-compatible)
# ---------------------------------------------------------------------------

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_REGION = os.getenv("S3_REGION", "auto")
S3_USE_SSL = env_bool("S3_USE_SSL", True)

# NP-155 backup retention (scripts also read env directly)
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))

# ---------------------------------------------------------------------------
# Observability (NP-183)
# ---------------------------------------------------------------------------

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development" if DEBUG else "production")
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", os.getenv("RELEASE", os.getenv("GIT_SHA", "")))
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1" if not DEBUG else "0"))

if SENTRY_DSN:
    from config.sentry import init_sentry

    init_sentry(
        dsn=SENTRY_DSN,
        release=SENTRY_RELEASE,
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
    )

# ---------------------------------------------------------------------------
# Invitations (MVP: link-based, no outbound email required)
# ---------------------------------------------------------------------------

INVITE_BASE_URL = os.getenv(
    "INVITE_BASE_URL",
    os.getenv("FRONTEND_URL", os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")),
).rstrip("/")
INVITE_EXPIRY_DAYS = int(os.getenv("INVITE_EXPIRY_DAYS", "7"))

# ---------------------------------------------------------------------------
# Integrations (NP-190) — Fernet key for IntegrationCredential ciphertext
# ---------------------------------------------------------------------------

INTEGRATIONS_FERNET_KEY = os.getenv("INTEGRATIONS_FERNET_KEY", "")

# KolayBi (NP-192) — mock mode for local/demo without live credentials
KOLAYBI_MOCK = env_bool("KOLAYBI_MOCK", False)
KOLAYBI_SANDBOX = env_bool("KOLAYBI_SANDBOX", True)
KOLAYBI_BASE_URL = os.getenv("KOLAYBI_BASE_URL", "")
