"""Shared settings. Environment-specific overrides live in development.py / production.py."""
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='dev-only-insecure-key-change-in-production')
DEBUG = env('DEBUG')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'axes',
    'apps.site',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Records the page view AFTER the response is built, so a slow write can
    # never delay the page. Must sit below auth so it can skip staff traffic.
    'apps.site.middleware.AnalyticsMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.site.context_processors.site_settings',
        ],
    },
}]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # WAL mode (set via the connection_created signal in apps.py — the
        # OPTIONS['init_command'] shortcut only exists from Django 5.1) lets the
        # analytics writer and page readers work concurrently instead of
        # tripping "database is locked" under even light traffic.
        'OPTIONS': {'timeout': 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Site-specific ────────────────────────────────────────────────────────────
SITE_NAME = 'Siphira John'
SITE_TAGLINE = 'Merchandiser, brand ambassador, and founder.'
SITE_EMAIL = 'siphirawanjiku0@gmail.com'
SITE_DOMAIN = env('SITE_DOMAIN', default='siphira.fluximpact.org')

# Salt for the daily visitor hash. Rotating it (or letting the date roll over)
# makes yesterday's hashes unlinkable to today's — that's what keeps the
# analytics genuinely anonymous rather than pseudonymous forever.
ANALYTICS_SALT = env('ANALYTICS_SALT', default='siphira-analytics-salt-change-me')

# Keyless push alerts (ntfy.sh). The droplet blocks outbound SMTP, so this is
# how a new message or comment actually reaches a phone.
NTFY_TOPIC = env('NTFY_TOPIC', default='')

# django-axes: lock out brute-force admin login attempts.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ['ip_address']
AXES_RESET_ON_SUCCESS = True

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
