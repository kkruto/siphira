"""Tests for the failure modes that actually bit this project.

Not exhaustive coverage — these target specific bugs that reached production,
so a regression is caught by `manage.py test` rather than by a reader noticing
developer notes printed on a page.
"""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Comment, Post, SiteSettings


TEMPLATE_DIRS = [
    Path(settings.BASE_DIR) / 'apps',
    Path(settings.BASE_DIR) / 'templates',
]


class TemplateCommentSyntaxTests(TestCase):
    """Django's {# #} comment is single-line ONLY.

    A multi-line one is not treated as a comment at all — the text renders
    straight onto the page. This shipped twice: developer notes appeared on
    /studio/ and on the admin login page.
    """

    def test_no_multiline_hash_comments(self):
        offenders = []
        for root in TEMPLATE_DIRS:
            for path in root.rglob('*.html'):
                for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                    if '{#' in line and '#}' not in line:
                        rel = path.relative_to(settings.BASE_DIR)
                        offenders.append(f'{rel}:{lineno}: {line.strip()[:70]}')

        self.assertEqual(
            offenders, [],
            'Multi-line {# #} comments render as visible page text. '
            'Use {% comment %}...{% endcomment %} instead:\n  '
            + '\n  '.join(offenders)
        )


class RenderedOutputTests(TestCase):
    """No template syntax should survive into rendered HTML."""

    LEAK = re.compile(
        r'\{#|#\}|\{%\s*(?:comment|endcomment|if|endif|for|endfor|block|'
        r'endblock|load|url|static)\b'
    )

    def setUp(self):
        SiteSettings.load()
        self.client = Client()

    def _assert_clean(self, path):
        response = self.client.get(path, follow=True)
        body = response.content.decode('utf-8', 'replace')
        # Script bodies legitimately contain braces.
        stripped = re.sub(r'<script.*?</script>', '', body, flags=re.S | re.I)
        match = self.LEAK.search(stripped)
        self.assertIsNone(
            match,
            f'{path} leaked template syntax: '
            f'{stripped[max(0, (match.start() - 60) if match else 0):][:160]!r}'
        )

    def test_public_pages_render_clean(self):
        for path in ['/', '/about/', '/projects/', '/blog/', '/skills/',
                     '/now/', '/contact/', '/cv/', '/privacy/', '/admin/login/']:
            with self.subTest(path=path):
                self._assert_clean(path)

    def test_staff_pages_render_clean(self):
        user = get_user_model().objects.create_superuser(
            'tester', 'tester@example.com', 'not-a-real-password-123')
        self.client.force_login(user)
        for path in ['/studio/', '/studio/analytics/', '/studio/inbox/',
                     '/studio/comments/', '/studio/feedback/', '/studio/posts/',
                     '/admin/']:
            with self.subTest(path=path):
                self._assert_clean(path)


class CommentModerationTests(TestCase):
    """Comments are approval-gated. A regression here publishes unreviewed
    text on her site, so it is worth a test rather than a code comment."""

    def setUp(self):
        SiteSettings.load()
        self.post = Post.objects.create(
            title='A post', slug='a-post', summary='Summary here.',
            body='Body text.', is_published=True)

    def test_new_comment_is_not_approved(self):
        response = self.client.post(
            f'/blog/{self.post.slug}/comment/',
            {'name': 'Reader', 'email': 'r@example.com', 'body': 'Nice post!'})
        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get()
        self.assertFalse(comment.is_approved, 'comments must await approval')

    def test_pending_comment_is_not_public(self):
        Comment.objects.create(
            post=self.post, name='Pending Person',
            email='secret@example.com', body='Not yet approved.')
        body = self.client.get(self.post.get_absolute_url()).content.decode()
        self.assertNotIn('Pending Person', body)
        self.assertNotIn('Not yet approved.', body)

    def test_approved_comment_is_public_but_email_is_not(self):
        Comment.objects.create(
            post=self.post, name='Approved Person',
            email='secret@example.com', body='Visible comment.',
            is_approved=True)
        body = self.client.get(self.post.get_absolute_url()).content.decode()
        self.assertIn('Approved Person', body)
        self.assertIn('Visible comment.', body)
        self.assertNotIn('secret@example.com', body,
                         'commenter emails must never be rendered publicly')

    def test_honeypot_submission_is_discarded(self):
        self.client.post(
            f'/blog/{self.post.slug}/comment/',
            {'name': 'Bot', 'email': 'bot@spam.com', 'body': 'Buy things',
             'website': 'http://spam.example'})
        self.assertEqual(Comment.objects.count(), 0)


class AnalyticsPrivacyTests(TestCase):
    """The privacy page promises no raw IPs are stored. Keep that true."""

    def test_pageview_has_no_raw_ip_field(self):
        from .models import PageView
        fields = {f.name for f in PageView._meta.get_fields()}
        for forbidden in ('ip', 'ip_address', 'remote_addr'):
            self.assertNotIn(forbidden, fields)

    def test_visitor_hash_rotates_daily(self):
        from .models import visitor_hash
        today = visitor_hash('1.2.3.4', 'Mozilla/5.0', day='2026-07-26')
        tomorrow = visitor_hash('1.2.3.4', 'Mozilla/5.0', day='2026-07-27')
        self.assertNotEqual(
            today, tomorrow,
            'the visitor hash must change daily or it becomes a durable id')

    def test_staff_traffic_is_not_counted(self):
        from .models import PageView
        user = get_user_model().objects.create_superuser(
            'owner', 'owner@example.com', 'not-a-real-password-123')
        self.client.force_login(user)
        self.client.get('/')
        self.assertEqual(PageView.objects.count(), 0)

    def test_bot_traffic_is_not_counted(self):
        from .models import PageView
        for agent in ('Googlebot/2.1', 'curl/8.0', 'python-requests/2.31'):
            self.client.get('/', HTTP_USER_AGENT=agent)
        self.assertEqual(PageView.objects.count(), 0)
