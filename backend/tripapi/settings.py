"""Django settings. Secrets and deployment values come from environment variables (see .env.example)."""

import os
from pathlib import Path

import dj_database_url

from agent.env import load_env

BASE_DIR = Path(__file__).resolve().parent.parent
load_env()  # repo-root .env (gitignored); added by Romir for local keys

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
# The trip page proxies /accounts/ and /api/me/ to Django (web/next.config.ts), so the sign-in
# cookie lives on the page's domain. Build URLs (e.g. Google's callback) from the host the browser
# used. Only safe behind that proxy; the host is still checked against ALLOWED_HOSTS.
USE_X_FORWARDED_HOST = os.environ.get("DJANGO_USE_X_FORWARDED_HOST", "1") == "1"

# Shared secret the agent sends as "Authorization: Bearer <token>" on /api/tools and /api/trips.
AGENT_API_TOKEN = os.environ.get("AGENT_API_TOKEN") or ("dev-agent-token" if DEBUG else None)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "trips",
    "bot",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Sign-in is Google only (django-allauth), no passwords. Credentials come from a
# Google Cloud OAuth client; see docs/google-signin.md.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SOCIALACCOUNT_ONLY = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # Google already verified the email
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        }],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}
# Where people land after signing in: the trip page.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
LOGIN_REDIRECT_URL = FRONTEND_URL
ACCOUNT_LOGOUT_REDIRECT_URL = FRONTEND_URL
LINK_CODE_MINUTES = 15

ROOT_URLCONF = "tripapi.urls"
WSGI_APPLICATION = "tripapi.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# SQLite locally; set DATABASE_URL (e.g. the Supabase Postgres connection string) to switch.
DATABASES = {"default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

# GroupMe bot. The callback URL to register with GroupMe is
# https://<host>/groupme/callback/<GROUPME_CALLBACK_SECRET>.
GROUPME_CALLBACK_SECRET = os.environ.get("GROUPME_CALLBACK_SECRET", "")
GROUPME_ACCESS_TOKEN = os.environ.get("GROUPME_ACCESS_TOKEN", "")  # only for BOT_DM_MODE=groupme
BOT_DM_MODE = os.environ.get("BOT_DM_MODE", "store")  # "store" (PrivateNotice) | "groupme" (DM API)
BOT_MENTION = os.environ.get("BOT_MENTION", "@tripbot")
BOT_FORWARD_ALL = os.environ.get("BOT_FORWARD_ALL", "0") == "1"  # also send un-mentioned messages to the agent
BOT_INLINE = os.environ.get("BOT_INLINE", "0") == "1"  # 1 = run the agent inside the webhook request (tests)

LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"bot": {"handlers": ["console"], "level": "INFO"}},
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
