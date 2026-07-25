import json
import logging
import re

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .middleware import client_ip
from .models import (
    Category, Comment, ContactMessage, Feedback, NowEntry, Post, Project,
    SiteSettings, SkillGroup, visitor_hash,
)
from .notify import push

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_URL_RE = re.compile(r'https?://|www\.', re.I)


# ─────────────────────────────────────────────────────────────────────────────
# Public pages
# ─────────────────────────────────────────────────────────────────────────────
def home(request):
    return render(request, 'site/home.html', {
        'recent_posts': Post.objects.published().select_related('category')[:3],
        'projects': Project.objects.filter(is_published=True)[:3],
        'now_entries': NowEntry.objects.filter(is_active=True)[:4],
    })


def about(request):
    return render(request, 'site/about.html', {
        'skill_groups': SkillGroup.objects.prefetch_related('skills'),
    })


def projects(request):
    return render(request, 'site/projects.html', {
        'projects': Project.objects.filter(is_published=True).prefetch_related('updates'),
    })


def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug, is_published=True)
    return render(request, 'site/project_detail.html', {
        'project': project,
        'updates': project.updates.all(),
        'images': project.images.all(),
    })


def blog_index(request):
    posts = Post.objects.published().select_related('category')

    active_category = None
    slug = request.GET.get('category')
    if slug:
        active_category = Category.objects.filter(slug=slug).first()
        if active_category:
            posts = posts.filter(category=active_category)

    query = request.GET.get('q', '').strip()
    if query:
        posts = posts.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
            | Q(body__icontains=query) | Q(tags__icontains=query)
        )

    paginator = Paginator(posts, 10)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'site/blog_index.html', {
        'page_obj': page,
        'posts': page.object_list,
        'categories': Category.objects.annotate(
            n=Count('posts', filter=Q(posts__is_published=True))).filter(n__gt=0),
        'active_category': active_category,
        'query': query,
    })


def post_detail(request, slug):
    post = get_object_or_404(
        Post.objects.published().select_related('category'), slug=slug)
    site = SiteSettings.load()

    related = Post.objects.published().exclude(pk=post.pk)
    if post.category:
        related = related.filter(category=post.category)
    return render(request, 'site/post_detail.html', {
        'post': post,
        'comments': post.approved_comments if site.comments_enabled else [],
        'comment_count': post.approved_comments.count() if site.comments_enabled else 0,
        'related': related[:2],
    })


def preview_post(request, slug):
    """Lets Siphira read an unpublished draft exactly as it will look live."""
    if not request.user.is_staff:
        raise Http404
    post = get_object_or_404(Post, slug=slug)
    return render(request, 'site/post_detail.html', {
        'post': post, 'comments': [], 'comment_count': 0,
        'related': [], 'is_preview': True,
    })


def skills(request):
    return render(request, 'site/skills.html', {
        'skill_groups': SkillGroup.objects.prefetch_related('skills'),
    })


def now(request):
    entries = NowEntry.objects.filter(is_active=True)
    grouped = []
    for key, label in NowEntry.KIND_CHOICES:
        items = [e for e in entries if e.kind == key]
        if items:
            grouped.append({'label': label, 'items': items})
    return render(request, 'site/now.html', {
        'grouped': grouped,
        'last_updated': entries.order_by('-updated_at').first(),
    })


def contact(request):
    return render(request, 'site/contact.html')


def cv(request):
    return render(request, 'site/cv.html')


def privacy(request):
    return render(request, 'site/privacy.html')


# ─────────────────────────────────────────────────────────────────────────────
# Form endpoints
# ─────────────────────────────────────────────────────────────────────────────
@require_POST
@ratelimit(key='ip', rate='5/m', block=False)
@ratelimit(key='ip', rate='20/d', block=False)
def contact_submit(request):
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'ok': False, 'error': 'Too many messages. Please try again later.'}, status=429)

    # Honeypot: a real browser leaves this hidden field empty. Bots fill it.
    # Answer 200-OK so the bot believes it succeeded and doesn't retry.
    if request.POST.get('website', '').strip():
        return JsonResponse({'ok': True})

    name = request.POST.get('name', '').strip()[:100]
    email = request.POST.get('email', '').strip()[:254]
    subject = request.POST.get('subject', '').strip()[:200]
    message = request.POST.get('message', '').strip()[:5000]

    errors = []
    if len(name) < 2:
        errors.append('Please enter your name.')
    if not _EMAIL_RE.match(email):
        errors.append('Please enter a valid email address.')
    if len(message) < 10:
        errors.append('Please write at least a sentence or two.')
    if errors:
        return JsonResponse({'ok': False, 'error': ' '.join(errors)}, status=400)

    msg = ContactMessage.objects.create(
        name=name, email=email, subject=subject, message=message,
        ip_hash=visitor_hash(client_ip(request), request.META.get('HTTP_USER_AGENT', '')),
        # Link-stuffed messages are almost always spam; flag rather than drop so
        # a false positive is still recoverable from the inbox.
        is_spam=len(_URL_RE.findall(message)) >= 3,
    )
    push(f'New message from {name}', f'{subject or "(no subject)"}\n\n{message[:200]}')
    logger.info('contact: message #%s from %s', msg.pk, email)
    return JsonResponse({'ok': True})


@require_POST
@ratelimit(key='ip', rate='3/m', block=False)
@ratelimit(key='ip', rate='15/d', block=False)
def comment_submit(request, slug):
    site = SiteSettings.load()
    if not site.comments_enabled:
        return JsonResponse({'ok': False, 'error': 'Comments are closed.'}, status=403)
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'ok': False, 'error': 'Too many comments. Please slow down.'}, status=429)
    if request.POST.get('website', '').strip():
        return JsonResponse({'ok': True})   # honeypot

    post = get_object_or_404(Post.objects.published(), slug=slug)

    name = request.POST.get('name', '').strip()[:100]
    email = request.POST.get('email', '').strip()[:254]
    body = request.POST.get('body', '').strip()[:3000]

    errors = []
    if len(name) < 2:
        errors.append('Please enter your name.')
    if not _EMAIL_RE.match(email):
        errors.append('Please enter a valid email address.')
    if len(body) < 3:
        errors.append('Please write a comment.')
    if errors:
        return JsonResponse({'ok': False, 'error': ' '.join(errors)}, status=400)

    Comment.objects.create(
        post=post, name=name, email=email, body=body,
        ip_hash=visitor_hash(client_ip(request), request.META.get('HTTP_USER_AGENT', '')),
        is_spam=len(_URL_RE.findall(body)) >= 2,
        # is_approved stays False — every comment waits for review.
    )
    push(f'New comment on “{post.title}”', f'{name}: {body[:180]}')
    return JsonResponse(
        {'ok': True, 'message': 'Thanks! Your comment will appear once Siphira approves it.'})


@require_POST
@ratelimit(key='ip', rate='10/m', block=False)
def feedback_submit(request):
    site = SiteSettings.load()
    if not site.feedback_enabled:
        return JsonResponse({'ok': False}, status=403)
    if getattr(request, 'limited', False):
        return JsonResponse({'ok': False}, status=429)

    sentiment = request.POST.get('sentiment')
    if sentiment not in ('up', 'down'):
        return JsonResponse({'ok': False, 'error': 'Invalid.'}, status=400)

    path = request.POST.get('path', '/')[:300]
    post = None
    if path.startswith('/blog/'):
        post = Post.objects.filter(slug=path.strip('/').split('/')[-1]).first()

    vh = visitor_hash(client_ip(request), request.META.get('HTTP_USER_AGENT', ''))
    note = request.POST.get('note', '').strip()[:1000]

    # One vote per visitor per page per day. `created_at` is auto_now_add, so it
    # can't be passed to update_or_create() — filter for today's row explicitly
    # and fall back to creating one.
    existing = Feedback.objects.filter(
        path=path, visitor_hash=vh, created_at__date=timezone.localdate()).first()
    if existing:
        existing.sentiment = sentiment
        existing.post = post
        if note:
            existing.note = note
        existing.is_read = False
        existing.save(update_fields=['sentiment', 'post', 'note', 'is_read'])
    else:
        Feedback.objects.create(
            path=path, visitor_hash=vh, sentiment=sentiment, post=post, note=note)
    return JsonResponse({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# Feeds, sitemap, health, errors
# ─────────────────────────────────────────────────────────────────────────────
def rss_feed(request):
    posts = Post.objects.published()[:20]
    base = f'{request.scheme}://{request.get_host()}'
    site = SiteSettings.load()

    def esc(s):
        return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

    items = ''.join(
        f'<item><title>{esc(p.title)}</title>'
        f'<link>{base}{p.get_absolute_url()}</link>'
        f'<guid isPermaLink="true">{base}{p.get_absolute_url()}</guid>'
        f'<description>{esc(p.summary)}</description>'
        f'<pubDate>{p.published_at.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate>'
        f'</item>'
        for p in posts
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f'<title>{esc(site.hero_name)}</title>'
        f'<link>{base}/blog/</link>'
        f'<description>{esc(site.blog_intro)}</description>'
        f'<language>en</language>{items}'
        '</channel></rss>'
    )
    return HttpResponse(xml, content_type='application/rss+xml')


def post_og_image(request, slug):
    """Branded link-preview card for a post. Cached hard — the content only
    changes when the post does, and the filename carries its mtime."""
    from . import og
    post = get_object_or_404(Post.objects.published(), slug=slug)
    response = HttpResponse(og.card_for_post(post), content_type='image/png')
    response['Cache-Control'] = 'public, max-age=604800'
    return response


def page_og_image(request, key):
    from . import og
    titles = {
        'home': 'Siphira John',
        'about': 'About Siphira',
        'projects': 'Projects',
        'blog': 'Writing',
        'contact': 'Get in touch',
    }
    if key not in titles:
        raise Http404
    response = HttpResponse(og.card_default(titles[key], key), content_type='image/png')
    response['Cache-Control'] = 'public, max-age=604800'
    return response


def robots_txt(request):
    base = f'{request.scheme}://{request.get_host()}'
    return HttpResponse(
        'User-agent: *\n'
        'Allow: /\n'
        'Disallow: /admin/\n'
        'Disallow: /studio/\n'
        f'Sitemap: {base}/sitemap.xml\n',
        content_type='text/plain',
    )


def healthz(request):
    return JsonResponse({'ok': True, 'time': timezone.now().isoformat()})


def handler404(request, exception=None):
    return render(request, 'site/404.html', status=404)


def handler500(request):
    return render(request, 'site/500.html', status=500)
