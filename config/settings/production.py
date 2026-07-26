from .base import *  # noqa: F401,F403
from .base import env, BASE_DIR

DEBUG = False

ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['siphira.fluximpact.org', 'www.siphira.fluximpact.org', '127.0.0.1', 'localhost'],
)
CSRF_TRUSTED_ORIGINS = ['https://siphira.fluximpact.org', 'https://www.siphira.fluximpact.org']

# nginx terminates TLS and proxies over plain HTTP on 127.0.0.1:8007, so Django
# has to be told the original scheme or it will redirect-loop on SECURE_SSL.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False           # nginx already 301s :80 → :443
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False   # shared parent domain — do not speak for siblings
SECURE_HSTS_PRELOAD = False

# WhiteNoise with hashed filenames + long cache headers. This is the whole
# static story — no nginx static block, no separate CDN.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # Deliberately the resilient subclass, not whitenoise's stock manifest
    # storage: a missing manifest entry should cost styling, not the whole
    # site. See config/storage.py.
    'staticfiles': {'BACKEND': 'config.storage.ResilientManifestStaticFilesStorage'},
}
WHITENOISE_MAX_AGE = 31536000

# Django configures logging during setup(), before any management command or
# deploy script gets a chance to run. If this directory is missing the
# RotatingFileHandler raises and the whole app fails to boot — so create it
# here rather than relying on deploy.sh having run first.
(BASE_DIR / 'logs').mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {name} {message}', 'style': '{'},
    },
    'handlers': {
        # Readable without root — same convention as the other apps on the box.
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'app.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'console': {'level': 'INFO', 'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['file', 'console'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'handlers': ['file', 'console'], 'level': 'ERROR', 'propagate': False},
        'apps.site': {'handlers': ['file', 'console'], 'level': 'INFO', 'propagate': False},
    },
}
