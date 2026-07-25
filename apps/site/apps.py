from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def set_sqlite_pragmas(sender, connection, **kwargs):
    """Put SQLite in WAL mode on every new connection.

    Without this, the analytics middleware writing a page view can block a
    concurrent read and surface as "database is locked". WAL lets readers and
    one writer proceed at the same time, which is exactly this workload.

    Django only grew `OPTIONS['init_command']` for SQLite in 5.1, so on 5.0 the
    signal is the supported hook.
    """
    if connection.vendor != 'sqlite':
        return
    cursor = connection.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')
    cursor.execute('PRAGMA synchronous=NORMAL;')
    cursor.execute('PRAGMA foreign_keys=ON;')


class SiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site'
    label = 'site'
    verbose_name = 'Site'
