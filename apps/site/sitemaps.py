from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post, Project


class StaticSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return ['home', 'about', 'projects_index', 'blog_index', 'skills', 'now', 'contact']

    def location(self, item):
        return reverse(item)


class PostSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Post.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class ProjectSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Project.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    'static': StaticSitemap,
    'posts': PostSitemap,
    'projects': ProjectSitemap,
}
