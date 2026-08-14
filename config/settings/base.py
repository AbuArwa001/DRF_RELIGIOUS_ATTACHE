"""
Base Django settings for the Quran Competition Portal.
"""

from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]
# Buffer files up to 10MB in RAM instead of writing to disk before S3 upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
# ALLOWED_HOSTS = ['*']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
raw_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [url.strip() for url in raw_origins.split(",") if url.strip()]

# ─── Applications ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    'storages',              # django-storages for AWS S3
    # Local
    'apps.competition',
    'apps.accounts',
]

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # must be first
    'django.middleware.gzip.GZipMiddleware',          # Compress API responses for extreme speed
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',      # i18n locale detection
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en'
USE_I18N = True
USE_L10N = True
USE_TZ = True

from django.utils.translation import gettext_lazy as _
LANGUAGES = [
    ('en', _('English')),
    ('ar', _('Arabic')),
]
LOCALE_PATHS = [BASE_DIR / 'locale']

# ─── Static & Media ───────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Password validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'NON_FIELD_ERRORS_KEY': 'errors',
}

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
# ─── AWS S3 Media Storage ─────────────────────────────────────────────────────
# Set USE_S3=True in your .env to enable cloud storage.
# When False (default in dev) uploads go to MEDIA_ROOT on the local filesystem.
USE_S3 = config('USE_S3', default=False, cast=bool)

if USE_S3:
    # ── Bucket & region ──────────────────────────────────────────────────────
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='religionattche')
    AWS_S3_REGION_NAME      = config('AWS_S3_REGION_NAME',      default='us-east-1')

    # ── Credentials (IAM user: jmcDonation) ─────────────────────────────────
    AWS_ACCESS_KEY_ID     = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')

    # ── Behaviour ────────────────────────────────────────────────────────────
    AWS_DEFAULT_ACL            = 'private'       # never make files public by default
    AWS_S3_FILE_OVERWRITE      = True            # replace file on re-upload (same key)
    AWS_QUERYSTRING_AUTH       = True            # use presigned URLs for access
    AWS_S3_SIGNATURE_VERSION   = 's3v4'          # required in most regions
    AWS_S3_OBJECT_PARAMETERS   = {
        'CacheControl': 'max-age=86400',
    }

    # ── Upload Optimization ──────────────────────────────────────────────────
    try:
        import boto3.s3.transfer
        AWS_S3_TRANSFER_CONFIG = boto3.s3.transfer.TransferConfig(
            use_threads=True,         # Enable multi-threaded uploads
            max_concurrency=10,       # Use up to 10 threads concurrently
            multipart_chunksize=8 * 1024 * 1024,  # 8 MB chunks (optimizes speed for standard files)
        )
    except ImportError:
        pass

    # ── Override default storage for uploaded media ──────────────────────────
    # Individual fields use their own storage class (PassportPhotoStorage /
    # IDDocumentStorage) defined in apps/competition/storage.py.  This default
    # also catches any other FileField that doesn't specify a custom storage.
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

    # When S3 is active, MEDIA_URL points at the bucket
    MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/'
