from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'testserver']
CSRF_TRUSTED_ORIGINS = ['http://localhost:8010', 'http://127.0.0.1:8010']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Serve the un-hashed static files directly in dev so there is no build step
# between editing tailwind.css and seeing it.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
