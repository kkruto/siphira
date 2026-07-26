from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Category, Comment, ContactMessage, DailyStat, Feedback, NowEntry, PageView,
    Post, Project, ProjectImage, ProjectUpdate, SiteSettings, Skill, SkillGroup,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Home page', {'fields': ('hero_name', 'hero_tagline', 'hero_intro', 'portrait')}),
        ('About', {'fields': ('about_body',)}),
        ('Section intros', {'fields': ('blog_intro', 'now_intro')}),
        ('Contact & links', {'fields': ('email', 'linkedin_url', 'twitter_url', 'location', 'cv')}),
        ('Switches', {'fields': ('comments_enabled', 'feedback_enabled')}),
    )

    def has_add_permission(self, request):
        # Singleton — the row is created by the seeder / load().
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'post_count')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('order',)

    @admin.display(description='Posts')
    def post_count(self, obj):
        return obj.posts.count()


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status_badge', 'published_at',
                    'read_time', 'view_count', 'comment_count')
    list_filter = ('is_published', 'is_featured', 'category', 'published_at')
    search_fields = ('title', 'summary', 'body', 'tags')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    readonly_fields = ('read_time', 'view_count', 'created_at', 'updated_at')
    actions = ('publish', 'unpublish')
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'summary', 'body')}),
        ('Presentation', {'fields': ('cover', 'cover_alt', 'category', 'tags')}),
        ('Publishing', {'fields': ('is_published', 'is_featured', 'published_at')}),
        ('Stats', {'fields': ('read_time', 'view_count', 'created_at', 'updated_at'),
                   'classes': ('collapse',)}),
    )

    class Media:
        # The stylesheet is loaded globally by templates/admin/base_site.html;
        # only the editor JS is page-specific, so listing the CSS here too
        # would just fetch it twice.
        js = ('admin/markdown-preview.js',)

    @admin.display(description='Status')
    def status_badge(self, obj):
        colour, label = ('#84A98C', 'Published') if obj.is_published else ('#B08968', 'Draft')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;'
            'font-size:11px;font-weight:600">{}</span>', colour, label)

    @admin.display(description='Comments')
    def comment_count(self, obj):
        return obj.comments.filter(is_approved=True).count()

    @admin.action(description='Publish selected posts')
    def publish(self, request, queryset):
        n = queryset.update(is_published=True)
        self.message_user(request, f'{n} post(s) published.')

    @admin.action(description='Unpublish selected posts')
    def unpublish(self, request, queryset):
        n = queryset.update(is_published=False)
        self.message_user(request, f'{n} post(s) unpublished.')


class ProjectUpdateInline(admin.TabularInline):
    model = ProjectUpdate
    extra = 1


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'is_published', 'order', 'updated_at')
    list_filter = ('status', 'is_published')
    list_editable = ('order', 'is_published')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProjectUpdateInline, ProjectImageInline]
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'tagline', 'status', 'cover', 'url')}),
        ('The story', {
            'fields': ('problem', 'approach', 'progress', 'lessons'),
            'description': 'Markdown. Leave any of these blank to hide that section.',
        }),
        ('Publishing', {'fields': ('is_published', 'order', 'started_at')}),
    )

    class Media:
        js = ('admin/markdown-preview.js',)


@admin.register(NowEntry)
class NowEntryAdmin(admin.ModelAdmin):
    list_display = ('kind', 'text', 'is_active', 'order', 'updated_at')
    list_filter = ('kind', 'is_active')
    list_editable = ('is_active', 'order')


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 3


@admin.register(SkillGroup)
class SkillGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'skill_count')
    list_editable = ('order',)
    inlines = [SkillInline]

    @admin.display(description='Skills')
    def skill_count(self, obj):
        return obj.skills.count()


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'is_archived',
                    'is_spam', 'created_at')
    list_filter = ('is_read', 'is_archived', 'is_spam', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'ip_hash', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('name', 'post', 'short_body', 'is_approved', 'is_spam', 'created_at')
    list_filter = ('is_approved', 'is_spam', 'created_at')
    search_fields = ('name', 'email', 'body')
    readonly_fields = ('name', 'email', 'body', 'post', 'ip_hash', 'created_at')
    actions = ('approve', 'mark_spam')

    @admin.display(description='Comment')
    def short_body(self, obj):
        return obj.body[:70] + ('…' if len(obj.body) > 70 else '')

    @admin.action(description='Approve selected comments')
    def approve(self, request, queryset):
        n = queryset.update(is_approved=True, is_spam=False)
        self.message_user(request, f'{n} comment(s) approved and now public.')

    @admin.action(description='Mark selected as spam')
    def mark_spam(self, request, queryset):
        n = queryset.update(is_spam=True, is_approved=False)
        self.message_user(request, f'{n} comment(s) marked as spam.')

    def has_add_permission(self, request):
        return False


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('sentiment', 'path', 'short_note', 'created_at')
    list_filter = ('sentiment', 'created_at')
    readonly_fields = ('path', 'post', 'sentiment', 'note', 'visitor_hash', 'created_at')

    @admin.display(description='Note')
    def short_note(self, obj):
        return (obj.note[:60] + '…') if len(obj.note) > 60 else obj.note

    def has_add_permission(self, request):
        return False


@admin.register(DailyStat)
class DailyStatAdmin(admin.ModelAdmin):
    list_display = ('date', 'views', 'visitors', 'top_path', 'top_referrer')
    readonly_fields = ('date', 'views', 'visitors', 'top_path', 'top_referrer')

    def has_add_permission(self, request):
        return False


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ('path', 'referrer_host', 'device', 'is_new_visitor', 'created_at')
    list_filter = ('device', 'is_new_visitor', 'created_at')
    readonly_fields = [f.name for f in PageView._meta.fields]

    def has_add_permission(self, request):
        return False
