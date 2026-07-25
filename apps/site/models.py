import hashlib
import math
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


# ─────────────────────────────────────────────────────────────────────────────
# Site-wide editable copy
# ─────────────────────────────────────────────────────────────────────────────
class SiteSettings(models.Model):
    """Singleton. Everything here is editable in admin so the home/about copy,
    links and CV can change without a code deploy."""

    hero_name = models.CharField(max_length=120, default='Siphira John')
    hero_tagline = models.CharField(
        max_length=300,
        default='Merchandiser, brand ambassador, and founder — building at the '
                'intersection of beauty, healthcare, and technology.',
    )
    hero_intro = models.TextField(
        default="I'm Siphira — a Nairobi-based merchandiser and field sales professional "
                'with a background in beauty, skincare, and haircare brand representation, '
                'and a certificate in orthopaedic and trauma medicine. I’m currently '
                'building something new. This site is where I document that journey.',
    )
    about_body = models.TextField(
        blank=True, help_text='Markdown. The full About page narrative.')
    now_intro = models.CharField(
        max_length=300,
        default="What I'm currently building, learning, reading, and focused on.")
    blog_intro = models.CharField(
        max_length=300,
        default='I write about entrepreneurship, technology, healthcare, AI, and design '
                '— reflections, tutorials, and lessons learned along the way.')

    email = models.EmailField(default='siphirawanjiku0@gmail.com')
    linkedin_url = models.URLField(
        blank=True, default='https://linkedin.com/in/siphira-john-b3b1a3314')
    twitter_url = models.URLField(
        blank=True, help_text='Full URL to the X/Twitter profile. Leave blank to hide.')
    location = models.CharField(max_length=100, default='Nairobi, Kenya')

    portrait = models.ImageField(
        upload_to='portraits/', blank=True,
        help_text='Overrides the bundled headshot if set.')
    cv = models.FileField(
        upload_to='cv/', blank=True,
        help_text='Overrides the bundled CV PDF if set.')

    comments_enabled = models.BooleanField(
        default=True, help_text='Global switch for blog comments.')
    feedback_enabled = models.BooleanField(
        default=True, help_text='Show the "was this useful?" widget on posts.')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return 'Site settings'

    def save(self, *args, **kwargs):
        # Enforce the singleton: there is only ever row 1.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Site settings cannot be deleted.')

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def portrait_url(self):
        return self.portrait.url if self.portrait else '/static/img/siphira.jpg'

    @property
    def cv_url(self):
        return self.cv.url if self.cv else '/static/files/siphira-john-cv.pdf'


# ─────────────────────────────────────────────────────────────────────────────
# Blog
# ─────────────────────────────────────────────────────────────────────────────
def _read_time(text):
    """Minutes, at 200 wpm, floor 1."""
    return max(1, math.ceil(len(re.findall(r'\w+', text or '')) / 200))


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog_index') + f'?category={self.slug}'


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(
        max_length=400, help_text='Shown on the blog index and in link previews.')
    body = models.TextField(help_text='Markdown supported.')
    cover = models.ImageField(upload_to='posts/', blank=True)
    cover_alt = models.CharField(
        max_length=200, blank=True, help_text='Describe the image for screen readers.')
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='posts')
    tags = models.CharField(
        max_length=200, blank=True, help_text='Comma-separated.')

    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    read_time = models.PositiveIntegerField(default=1, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ['-published_at']
        indexes = [models.Index(fields=['-published_at', 'is_published'])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        self.read_time = _read_time(self.body)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'slug': self.slug})

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def approved_comments(self):
        return self.comments.filter(is_approved=True).order_by('created_at')


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────
class Project(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In progress'),
        ('live', 'Live'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')

    # The four-part structure her brief asks for. Each is optional so a project
    # can go up as a stub and fill in over time.
    problem = models.TextField(blank=True, help_text='Markdown. What problem is this solving?')
    approach = models.TextField(blank=True, help_text='Markdown. How are you approaching it?')
    progress = models.TextField(blank=True, help_text='Markdown. Where things stand.')
    lessons = models.TextField(blank=True, help_text='Markdown. What you have learned.')

    cover = models.ImageField(upload_to='projects/', blank=True)
    url = models.URLField(blank=True, help_text='Live site, if there is one.')
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    started_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-updated_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('project_detail', kwargs={'slug': self.slug})

    @property
    def status_tone(self):
        """Maps status → a palette token, so templates don't hardcode colours."""
        return {
            'in_progress': 'sage',
            'live': 'sage',
            'paused': 'sand',
            'archived': 'muted',
        }.get(self.status, 'sage')


class ProjectUpdate(models.Model):
    """A dated entry on a project's timeline."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='updates')
    date = models.DateField(default=timezone.localdate)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(help_text='Markdown.')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.project.name} — {self.date}'


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='projects/shots/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.caption or f'Screenshot {self.pk}'


# ─────────────────────────────────────────────────────────────────────────────
# Now page + skills
# ─────────────────────────────────────────────────────────────────────────────
class NowEntry(models.Model):
    KIND_CHOICES = [
        ('building', 'Building'),
        ('learning', 'Learning'),
        ('reading', 'Reading'),
        ('focused', 'Focused on'),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='building')
    text = models.CharField(max_length=300)
    detail = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'order']
        verbose_name_plural = 'Now entries'

    def __str__(self):
        return f'{self.get_kind_display()}: {self.text}'


class SkillGroup(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=250, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Skill(models.Model):
    group = models.ForeignKey(SkillGroup, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────────────
# Inbox, comments, feedback
# ─────────────────────────────────────────────────────────────────────────────
class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()

    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.subject or "(no subject)"}'


class Comment(models.Model):
    """Approval-gated: nothing shows publicly until Siphira approves it.

    The commenter's email is collected for reply/identification only and is
    never rendered in a public template.
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=100)
    email = models.EmailField(help_text='Never shown publicly.')
    body = models.TextField(max_length=3000)

    is_approved = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['is_approved', '-created_at'])]

    def __str__(self):
        return f'{self.name} on {self.post.title}'

    @property
    def initial(self):
        return (self.name.strip()[:1] or '?').upper()


class Feedback(models.Model):
    """The 'was this useful?' widget. Sentiment plus an optional note."""
    SENTIMENT_CHOICES = [('up', 'Helpful'), ('down', 'Not helpful')]

    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.CASCADE, related_name='feedback')
    path = models.CharField(max_length=300)
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES)
    note = models.TextField(max_length=1000, blank=True)
    visitor_hash = models.CharField(max_length=64, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Feedback'

    def __str__(self):
        return f'{self.get_sentiment_display()} — {self.path}'


# ─────────────────────────────────────────────────────────────────────────────
# Analytics — first-party, cookieless, no raw IPs stored
# ─────────────────────────────────────────────────────────────────────────────
def visitor_hash(ip, user_agent, day=None):
    """A daily-rotating anonymous visitor id.

    The raw IP is never persisted. Because the day is part of the digest,
    a given person's hash changes at midnight, so views cannot be chained
    into a long-term profile — which is the point.
    """
    day = day or timezone.localdate().isoformat()
    raw = f'{settings.ANALYTICS_SALT}|{day}|{ip or ""}|{user_agent or ""}'
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class PageView(models.Model):
    DEVICE_CHOICES = [('desktop', 'Desktop'), ('mobile', 'Mobile'), ('tablet', 'Tablet')]

    path = models.CharField(max_length=300, db_index=True)
    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.SET_NULL, related_name='views')
    referrer_host = models.CharField(max_length=150, blank=True)
    country = models.CharField(max_length=60, blank=True)
    device = models.CharField(max_length=10, choices=DEVICE_CHOICES, default='desktop')
    visitor = models.CharField(max_length=32, db_index=True)
    is_new_visitor = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at', 'path'])]

    def __str__(self):
        return f'{self.path} @ {self.created_at:%Y-%m-%d %H:%M}'


class DailyStat(models.Model):
    """Nightly rollup so the dashboard never scans the raw PageView table.

    Raw views are pruned after the rollup (see `rollup_analytics`), which keeps
    the SQLite file small and means we don't sit on visitor-level data forever.
    """
    date = models.DateField(unique=True)
    views = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    top_path = models.CharField(max_length=300, blank=True)
    top_referrer = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.date}: {self.views} views'
