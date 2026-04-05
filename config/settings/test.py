"""Test settings — fast hashing, SQLite in-memory, no migrations for speed."""
from .base import *  # noqa: F401, F403

DEBUG = True  # noqa: F811
SECRET_KEY = "test-secret-key-not-for-production"  # noqa: F811

# Use faster password hasher in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# In-memory SQLite for speed (override with POSTGRES_DB env var for integration tests)
import os as _os  # noqa: E402

if not _os.environ.get("DATABASE_URL") and not _os.environ.get("USE_POSTGRES_IN_TESTS"):
    from pathlib import Path as _Path

    DATABASES = {  # noqa: F811
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"  # noqa: F811

# Silence logging in tests
LOGGING = {  # noqa: F811
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
}
