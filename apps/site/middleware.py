"""First-party, cookieless page-view recording.

Design constraints that shaped this:
  * Never delay a response — the write happens after the body is produced, and
    any failure is swallowed (analytics must never 500 a page).
  * Never store a raw IP — see `visitor_hash`, which is salted and rotates daily.
  * Never count Siphira's own traffic, bots, or non-page requests.
"""
import logging
import re
from urllib.parse import urlparse

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Substring match against a lowercased UA. Deliberately broad: over-excluding a
# real visitor costs one uncounted view, under-excluding pollutes every number.
BOT_MARKERS = (
    'bot', 'crawl', 'spider', 'slurp', 'curl', 'wget', 'python-requests',
    'httpx', 'headless', 'lighthouse', 'pingdom', 'uptime', 'monitor',
    'facebookexternalhit', 'preview', 'scan', 'go-http-client', 'okhttp',
    'postman', 'insomnia', 'axios', 'node-fetch', 'phantomjs', 'selenium',
)

# Paths that are never "a page someone read".
SKIP_PREFIXES = (
    '/static/', '/media/', '/admin/', '/studio/', '/favicon', '/robots.txt',
    '/sitemap.xml', '/feed/', '/healthz',
)

_MOBILE_RE = re.compile(r'mobi|android|iphone|ipod|windows phone', re.I)
_TABLET_RE = re.compile(r'ipad|tablet|kindle|silk|playbook', re.I)


def _device(ua):
    if _TABLET_RE.search(ua):
        return 'tablet'
    if _MOBILE_RE.search(ua):
        return 'mobile'
    return 'desktop'


def client_ip(request):
    """Real client IP behind nginx.

    X-Real-IP is set by our own nginx block and is therefore trustworthy here;
    X-Forwarded-For is only consulted as a fallback and we take the FIRST entry.
    """
    real = request.META.get('HTTP_X_REAL_IP')
    if real:
        return real.strip()
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class AnalyticsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        try:
            self._record(request, response)
        except Exception:  # analytics is never allowed to break a page
            logger.exception('analytics: failed to record page view')
        return response

    def _record(self, request, response):
        if request.method != 'GET' or response.status_code != 200:
            return
        # Only count real HTML page loads, not fetch()/JSON or asset requests.
        if 'text/html' not in response.get('Content-Type', ''):
            return

        path = request.path
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return

        ua = request.META.get('HTTP_USER_AGENT', '')
        ua_low = ua.lower()
        if not ua or any(m in ua_low for m in BOT_MARKERS):
            return

        # Don't count the owner browsing her own site.
        if getattr(request, 'user', None) and request.user.is_authenticated:
            return

        from .models import PageView, Post, visitor_hash

        vh = visitor_hash(client_ip(request), ua)

        referrer_host = ''
        ref = request.META.get('HTTP_REFERER', '')
        if ref:
            host = (urlparse(ref).hostname or '').lower()
            # Internal navigation isn't a referrer worth reporting.
            if host and host not in request.get_host().lower():
                referrer_host = host.removeprefix('www.')[:150]

        post = None
        if path.startswith('/blog/') and path.count('/') == 3:
            post = Post.objects.filter(slug=path.strip('/').split('/')[-1]).first()

        PageView.objects.create(
            path=path[:300],
            post=post,
            referrer_host=referrer_host,
            device=_device(ua),
            visitor=vh,
            is_new_visitor=not PageView.objects.filter(visitor=vh).exists(),
        )

        if post:
            # F() so concurrent readers can't clobber each other's increment.
            from django.db.models import F
            Post.objects.filter(pk=post.pk).update(view_count=F('view_count') + 1)
