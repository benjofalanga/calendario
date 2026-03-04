import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "replace-this-with-a-real-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "timeoff.apps.TimeoffConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "calendario.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "timeoff.context_processors.role_flags",
            ],
        },
    }
]

WSGI_APPLICATION = "calendario.wsgi.application"
ASGI_APPLICATION = "calendario.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "timeoff" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Default: local Django auth only.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Optional LDAP login support.
ENABLE_LDAP_AUTH = _env_bool("ENABLE_LDAP_AUTH", False)
if ENABLE_LDAP_AUTH:
    try:
        import ldap
        from django_auth_ldap.config import LDAPSearch, MemberDNGroupType
    except ImportError as exc:
        raise ImproperlyConfigured(
            "ENABLE_LDAP_AUTH is true, but LDAP dependencies are missing. "
            "Install django-auth-ldap and python-ldap."
        ) from exc

    AUTHENTICATION_BACKENDS = [
        "django_auth_ldap.backend.LDAPBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]

    AUTH_LDAP_SERVER_URI = os.getenv("AUTH_LDAP_SERVER_URI", "ldap://localhost:389")
    AUTH_LDAP_BIND_DN = os.getenv("AUTH_LDAP_BIND_DN", "")
    AUTH_LDAP_BIND_PASSWORD = os.getenv("AUTH_LDAP_BIND_PASSWORD", "")
    AUTH_LDAP_START_TLS = _env_bool("AUTH_LDAP_START_TLS", False)

    # Example user filter:
    # AD: (sAMAccountName=%(user)s)
    # OpenLDAP: (uid=%(user)s)
    AUTH_LDAP_USER_BASE_DN = os.getenv("AUTH_LDAP_USER_BASE_DN", "")
    AUTH_LDAP_USER_FILTER = os.getenv("AUTH_LDAP_USER_FILTER", "(uid=%(user)s)")

    if not AUTH_LDAP_USER_BASE_DN:
        raise ImproperlyConfigured(
            "ENABLE_LDAP_AUTH is true but AUTH_LDAP_USER_BASE_DN is empty."
        )

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        AUTH_LDAP_USER_BASE_DN,
        ldap.SCOPE_SUBTREE,
        AUTH_LDAP_USER_FILTER,
    )

    AUTH_LDAP_USER_ATTR_MAP = {
        "first_name": os.getenv("AUTH_LDAP_ATTR_FIRST_NAME", "givenName"),
        "last_name": os.getenv("AUTH_LDAP_ATTR_LAST_NAME", "sn"),
        "email": os.getenv("AUTH_LDAP_ATTR_EMAIL", "mail"),
    }
    AUTH_LDAP_ALWAYS_UPDATE_USER = _env_bool("AUTH_LDAP_ALWAYS_UPDATE_USER", True)

    # Optional group-based access controls.
    AUTH_LDAP_REQUIRE_GROUP_DN = os.getenv("AUTH_LDAP_REQUIRE_GROUP_DN", "").strip()
    AUTH_LDAP_MANAGER_GROUP_DN = os.getenv("AUTH_LDAP_MANAGER_GROUP_DN", "").strip()
    AUTH_LDAP_GROUP_BASE_DN = os.getenv("AUTH_LDAP_GROUP_BASE_DN", "").strip()
    AUTH_LDAP_GROUP_FILTER = os.getenv(
        "AUTH_LDAP_GROUP_FILTER",
        "(objectClass=groupOfNames)",
    )

    if AUTH_LDAP_GROUP_BASE_DN:
        AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
            AUTH_LDAP_GROUP_BASE_DN,
            ldap.SCOPE_SUBTREE,
            AUTH_LDAP_GROUP_FILTER,
        )
        AUTH_LDAP_GROUP_TYPE = MemberDNGroupType()

    if AUTH_LDAP_REQUIRE_GROUP_DN:
        AUTH_LDAP_REQUIRE_GROUP = AUTH_LDAP_REQUIRE_GROUP_DN

    if AUTH_LDAP_MANAGER_GROUP_DN:
        AUTH_LDAP_USER_FLAGS_BY_GROUP = {
            "is_staff": AUTH_LDAP_MANAGER_GROUP_DN,
        }

    AUTH_LDAP_CACHE_TIMEOUT = _env_int("AUTH_LDAP_CACHE_TIMEOUT", 3600)
