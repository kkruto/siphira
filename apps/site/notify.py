"""Keyless push notifications via ntfy.sh.

DigitalOcean blocks outbound SMTP on the droplet, so email is not a reliable
delivery path for "you have a new message". ntfy needs no account or API key:
subscribe to the topic in the ntfy app and posts to it arrive as phone
notifications.

Every call is best-effort and short-timeout — a notification failure must never
affect the request that triggered it.
"""
import logging
import threading
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def _post(topic, title, body):
    try:
        req = urllib.request.Request(
            f'https://ntfy.sh/{topic}',
            data=body.encode('utf-8')[:3000],
            headers={'Title': title[:200], 'Priority': 'default', 'Tags': 'bell'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as exc:
        logger.warning('notify: push failed (%s)', exc)


def push(title, body=''):
    """Fire-and-forget. Returns immediately; the HTTP call runs on a daemon
    thread so a slow ntfy can never hold a page response open."""
    topic = getattr(settings, 'NTFY_TOPIC', '')
    if not topic:
        return
    threading.Thread(target=_post, args=(topic, title, body), daemon=True).start()
