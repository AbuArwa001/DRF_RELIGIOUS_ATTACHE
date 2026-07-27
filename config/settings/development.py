"""
Development settings — SQLite, DEBUG on, permissive CORS.
"""
from .base import *  # noqa

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Show browsable API in dev
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (  # noqa
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
)
