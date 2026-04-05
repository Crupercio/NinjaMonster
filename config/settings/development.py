"""Development settings — debug mode, relaxed security, SQLite fallback allowed."""
import os

from .base import *  # noqa: F401, F403

DEBUG = True
SECRET_KEY = os.environ.get(  # noqa: F811 — override base
    "SECRET_KEY",
    "django-insecure-dev-only-change-in-production-never-use-this-key",
)

ALLOWED_HOSTS = ["*"]

# Show all SQL queries in debug
LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "DEBUG",
    "propagate": False,
}

# Email backend — print to console during development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Development database fallback — use SQLite if no DATABASE_URL is set
# ---------------------------------------------------------------------------
import os as _os  # noqa: E402

if not _os.environ.get("DATABASE_URL") and not _os.environ.get("POSTGRES_DB"):
    from pathlib import Path as _Path

    _BASE_DIR = _Path(__file__).resolve().parent.parent.parent
    DATABASES = {  # noqa: F811
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _BASE_DIR / "db.sqlite3",
        }
    }
