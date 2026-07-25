from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import studio, views
from .sitemaps import SITEMAPS

urlpatterns = [
    # ── Public ──────────────────────────────────────────────────────────────
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('projects/', views.projects, name='projects_index'),
    path('projects/<slug:slug>/', views.project_detail, name='project_detail'),
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/<slug:slug>/', views.post_detail, name='post_detail'),
    path('blog/<slug:slug>/og.png', views.post_og_image, name='post_og_image'),
    path('blog/<slug:slug>/comment/', views.comment_submit, name='comment_submit'),
    path('drafts/<slug:slug>/', views.preview_post, name='preview_post'),
    path('skills/', views.skills, name='skills'),
    path('now/', views.now, name='now'),
    path('contact/', views.contact, name='contact'),
    path('contact/submit/', views.contact_submit, name='contact_submit'),
    path('feedback/', views.feedback_submit, name='feedback_submit'),
    path('cv/', views.cv, name='cv'),
    path('privacy/', views.privacy, name='privacy'),

    # ── Machine-readable ────────────────────────────────────────────────────
    path('feed/', views.rss_feed, name='rss_feed'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='django.contrib.sitemaps.views.sitemap'),
    path('og/<str:key>.png', views.page_og_image, name='page_og_image'),
    path('healthz/', views.healthz, name='healthz'),

    # ── Studio (staff only) ─────────────────────────────────────────────────
    path('studio/', studio.dashboard, name='studio'),
    path('studio/inbox/', studio.inbox, name='studio_inbox'),
    path('studio/inbox/<int:pk>/', studio.inbox_detail, name='studio_inbox_detail'),
    path('studio/inbox/<int:pk>/action/', studio.inbox_action, name='studio_inbox_action'),
    path('studio/comments/', studio.comments, name='studio_comments'),
    path('studio/comments/<int:pk>/action/', studio.comment_action, name='studio_comment_action'),
    path('studio/feedback/', studio.feedback, name='studio_feedback'),
    path('studio/analytics/', studio.analytics, name='studio_analytics'),
    path('studio/posts/', studio.posts, name='studio_posts'),
    path('studio/posts/<int:pk>/publish/', studio.post_publish, name='studio_post_publish'),
]
