"""
Configuración del proyecto Django (frontend).

Ver: https://docs.djangoproject.com/en/5.1/topics/settings/
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: cambia esta clave y no la subas a un repo público.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-cambia-esta-clave-en-produccion")

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
# Vercel usa un dominio dinámico *.vercel.app; se agrega automáticamente.
if os.getenv("VERCEL_URL"):
    ALLOWED_HOSTS.append(os.getenv("VERCEL_URL"))
    CSRF_TRUSTED_ORIGINS = [f"https://{os.getenv('VERCEL_URL')}"]

# Seguridad en producción: detrás del proxy HTTPS de Vercel/Render.
if os.getenv("DJANGO_DEBUG", "True") != "True":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False  # Vercel ya termina TLS; no redirigir en la app


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "capture",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sirve estáticos en Vercel (serverless)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# - En producción (Vercel) el filesystem de la función serverless es de solo
#   lectura salvo /tmp y cada invocación puede correr en una instancia nueva,
#   por lo que SQLite no persiste. Se usa DATABASE_URL apuntando a un Postgres
#   externo (Neon, Supabase, Vercel Postgres...).
# - En desarrollo local sin DATABASE_URL se cae de vuelta a SQLite (cómodo).
import dj_database_url  # type: ignore

_DEFAULT_SQLITE_URL = "sqlite:///" + str(BASE_DIR / "db.sqlite3").replace("\\", "/")

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DJANGO_DB_PATH", _DEFAULT_SQLITE_URL),
        conn_max_age=600,
    )
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Configuración propia del proyecto --------------------------------------

# URL base del backend FastAPI (reconocimiento facial + JWT).
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8001")

# A dónde redirige Django tras login/logout (auth por sesión de Django).
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "capture:capture"
LOGOUT_REDIRECT_URL = "accounts:login"
