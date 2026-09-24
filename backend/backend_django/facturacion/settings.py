from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "True") == "True"


def _lista_env(nombre, por_defecto=""):
    """Lee una variable de entorno separada por comas y la devuelve como lista."""
    return [v.strip() for v in os.environ.get(nombre, por_defecto).split(",") if v.strip()]


# En local (DEBUG=True) se acepta cualquier host; en producción hay que declarar
# los dominios reales en ALLOWED_HOSTS del .env.
ALLOWED_HOSTS = ["*"] if DEBUG else _lista_env("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "facturacion.urls"
WSGI_APPLICATION = "facturacion.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "facturacion"),
        "USER": os.environ.get("DB_USER", "facturacion_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "facturacion_pass"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

APPEND_SLASH = False

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Media / uploads
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
UPLOAD_DIR = MEDIA_ROOT / "uploads"
GENERATED_PDF_DIR = MEDIA_ROOT / "generated_pdfs"

# Último número de cotización emitido fuera del sistema. Las cotizaciones del
# sistema siguen desde ahí: con 159, la primera sale 160-2026.
COTIZACION_CONSECUTIVO_INICIAL = int(os.environ.get("COTIZACION_CONSECUTIVO_INICIAL", "0"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.auth_backend.FacturacionJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # El formulario público de vinculación no pide login, así que se limita por IP.
    "DEFAULT_THROTTLE_RATES": {
        "vinculacion_publica": "20/hour",
        "solicitud_publica": "30/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

CORS_ALLOW_CREDENTIALS = True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # Detrás de nginx el frontend se sirve en el mismo origen que /api, así que
    # normalmente esta lista puede quedar vacía.
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = _lista_env("CORS_ALLOWED_ORIGINS")

# nginx termina el TLS y reenvía por http, así que Django necesita esta cabecera
# para saber que la petición original venía por https.
CSRF_TRUSTED_ORIGINS = _lista_env("CSRF_TRUSTED_ORIGINS")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# Correo — para avisar a las plantas cuando se les emite una orden de suministro.
# Sin EMAIL_HOST, el botón "Correo" responde que no está configurado (y en
# desarrollo los correos salen por consola).
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
    EMAIL_CONFIGURADO = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    EMAIL_CONFIGURADO = False
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or os.environ.get("EMAIL_HOST_USER") or "no-reply@cofilatam.com"

# Dirección pública de la app, para los links que van en WhatsApp y correo
# (p. ej. https://facturacion.cofilatam.com). Vacía = se deduce de la petición.
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
