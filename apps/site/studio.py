"""Staff-only control room at /studio/.

Django admin still exists for raw CRUD; this is the human-facing layer —
traffic at a glance, an inbox that reads like an inbox, and a moderation queue
where approving a comment is one click rather than a change-form.
"""
import datetime
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Comment, ContactMessage, DailyStat, Feedback, PageView, Post,
)

RANGE_CHOICES = {'7': 7, '30': 30, '90': 90}


def _range_days(request, default=30):
    return RANGE_CHOICES.get(request.GET.get('range'), default)


def _traffic_series(days):
    """Daily views/visitors for the last N days, zero-filled.

    Reads the rolled-up DailyStat table for past days and the live PageView
    table for today (which has not been rolled up yet), so the chart is
    accurate right up to the current minute.
    """
    today = timezone.localdate()
    start = today - datetime.timedelta(days=days - 1)

    rolled = {s.date: s for s in DailyStat.objects.filter(date__gte=start, date__lt=today)}

    live = (PageView.objects
            .filter(created_at__date=today)
            .aggregate(views=Count('id'), visitors=Count('visitor', distinct=True)))

    series = []
    for i in range(days):
        day = start + datetime.timedelta(days=i)
        if day == today:
            series.append({'date': day.isoformat(),
                           'views': live['views'] or 0,
                           'visitors': live['visitors'] or 0})
        elif day in rolled:
            series.append({'date': day.isoformat(),
                           'views': rolled[day].views,
                           'visitors': rolled[day].visitors})
        else:
            series.append({'date': day.isoformat(), 'views': 0, 'visitors': 0})
    return series


@staff_member_required
def dashboard(request):
    days = _range_days(request)
    series = _traffic_series(days)
    since = timezone.now() - datetime.timedelta(days=days)

    total_views = sum(d['views'] for d in series)
    total_visitors = sum(d['visitors'] for d in series)

    # Previous window of the same length, for the trend arrow.
    prev = _traffic_series(days * 2)[:days]
    prev_views = sum(d['views'] for d in prev)
    delta = round((total_views - prev_views) / prev_views * 100) if prev_views else None

    recent_views = PageView.objects.filter(created_at__gte=since)

    return render(request, 'studio/dashboard.html', {
        'active': 'dashboard',
        'days': days,
        'series_json': json.dumps(series),
        'total_views': total_views,
        'total_visitors': total_visitors,
        'delta': delta,
        'top_posts': (Post.objects.published()
                      .annotate(recent=Count('views', filter=Q(views__created_at__gte=since)))
                      .order_by('-recent', '-view_count')[:5]),
        'top_paths': (recent_views.values('path')
                      .annotate(n=Count('id')).order_by('-n')[:6]),
        'top_referrers': (recent_views.exclude(referrer_host='')
                          .values('referrer_host')
                          .annotate(n=Count('id')).order_by('-n')[:6]),
        'devices': (recent_views.values('device')
                    .annotate(n=Count('id')).order_by('-n')),
        'unread_messages': ContactMessage.objects.filter(
            is_read=False, is_archived=False, is_spam=False).count(),
        'pending_comments': Comment.objects.filter(is_approved=False, is_spam=False).count(),
        'unread_feedback': Feedback.objects.filter(is_read=False).count(),
        'draft_count': Post.objects.filter(is_published=False).count(),
        'latest_messages': ContactMessage.objects.filter(is_archived=False)[:5],
        'latest_comments': Comment.objects.filter(is_approved=False, is_spam=False)[:5],
    })


@staff_member_required
def analytics(request):
    days = _range_days(request, 30)
    series = _traffic_series(days)
    since = timezone.now() - datetime.timedelta(days=days)
    views = PageView.objects.filter(created_at__gte=since)

    return render(request, 'studio/analytics.html', {
        'active': 'analytics',
        'days': days,
        'series_json': json.dumps(series),
        'total_views': sum(d['views'] for d in series),
        'total_visitors': sum(d['visitors'] for d in series),
        'new_visitors': views.filter(is_new_visitor=True).count(),
        'top_paths': views.values('path').annotate(n=Count('id')).order_by('-n')[:15],
        'top_referrers': (views.exclude(referrer_host='').values('referrer_host')
                          .annotate(n=Count('id')).order_by('-n')[:15]),
        'devices': views.values('device').annotate(n=Count('id')).order_by('-n'),
        'posts': (Post.objects.published()
                  .annotate(recent=Count('views', filter=Q(views__created_at__gte=since)))
                  .order_by('-recent')[:15]),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Inbox
# ─────────────────────────────────────────────────────────────────────────────
@staff_member_required
def inbox(request):
    box = request.GET.get('box', 'inbox')
    qs = ContactMessage.objects.all()
    if box == 'archived':
        qs = qs.filter(is_archived=True)
    elif box == 'spam':
        qs = qs.filter(is_spam=True)
    else:
        qs = qs.filter(is_archived=False, is_spam=False)

    return render(request, 'studio/inbox.html', {
        'active': 'inbox',
        'messages_list': qs[:100],
        'box': box,
        'counts': {
            'inbox': ContactMessage.objects.filter(is_archived=False, is_spam=False).count(),
            'archived': ContactMessage.objects.filter(is_archived=True).count(),
            'spam': ContactMessage.objects.filter(is_spam=True).count(),
        },
    })


@staff_member_required
def inbox_detail(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    if not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=['is_read'])
    return render(request, 'studio/inbox_detail.html', {'msg': msg, 'active': 'inbox'})


@staff_member_required
@require_POST
def inbox_action(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    action = request.POST.get('action')

    if action == 'archive':
        msg.is_archived = True
    elif action == 'unarchive':
        msg.is_archived = False
    elif action == 'spam':
        msg.is_spam, msg.is_archived = True, True
    elif action == 'not_spam':
        msg.is_spam, msg.is_archived = False, False
    elif action == 'read':
        msg.is_read = True
    elif action == 'unread':
        msg.is_read = False
    elif action == 'delete':
        msg.delete()
        return redirect('studio_inbox')
    else:
        return JsonResponse({'ok': False, 'error': 'Unknown action'}, status=400)

    msg.save()
    return redirect(request.POST.get('next') or 'studio_inbox')


# ─────────────────────────────────────────────────────────────────────────────
# Comment moderation
# ─────────────────────────────────────────────────────────────────────────────
@staff_member_required
def comments(request):
    state = request.GET.get('state', 'pending')
    qs = Comment.objects.select_related('post')
    if state == 'approved':
        qs = qs.filter(is_approved=True)
    elif state == 'spam':
        qs = qs.filter(is_spam=True)
    else:
        qs = qs.filter(is_approved=False, is_spam=False)

    return render(request, 'studio/comments.html', {
        'active': 'comments',
        'comments': qs.order_by('-created_at')[:100],
        'state': state,
        'counts': {
            'pending': Comment.objects.filter(is_approved=False, is_spam=False).count(),
            'approved': Comment.objects.filter(is_approved=True).count(),
            'spam': Comment.objects.filter(is_spam=True).count(),
        },
    })


@staff_member_required
@require_POST
def comment_action(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    action = request.POST.get('action')

    if action == 'approve':
        comment.is_approved, comment.is_spam = True, False
    elif action == 'unapprove':
        comment.is_approved = False
    elif action == 'spam':
        comment.is_spam, comment.is_approved = True, False
    elif action == 'delete':
        comment.delete()
        return redirect(request.POST.get('next') or 'studio_comments')
    else:
        return JsonResponse({'ok': False, 'error': 'Unknown action'}, status=400)

    comment.save()
    return redirect(request.POST.get('next') or 'studio_comments')


# ─────────────────────────────────────────────────────────────────────────────
# Feedback + posts
# ─────────────────────────────────────────────────────────────────────────────
@staff_member_required
def feedback(request):
    items = Feedback.objects.select_related('post')[:200]
    up = Feedback.objects.filter(sentiment='up').count()
    down = Feedback.objects.filter(sentiment='down').count()

    # Mark the batch as seen so the dashboard badge clears.
    Feedback.objects.filter(is_read=False).update(is_read=True)

    return render(request, 'studio/feedback.html', {
        'active': 'feedback',
        'items': items,
        'up': up,
        'down': down,
        'total': up + down,
        'by_page': (Feedback.objects.values('path')
                    .annotate(n=Count('id'),
                              helpful=Count('id', filter=Q(sentiment='up')))
                    .order_by('-n')[:15]),
    })


@staff_member_required
def posts(request):
    return render(request, 'studio/posts.html', {
        'active': 'posts',
        'drafts': Post.objects.filter(is_published=False).order_by('-updated_at'),
        'published': Post.objects.published().order_by('-published_at')[:50],
    })


@staff_member_required
@require_POST
def post_publish(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.is_published = not post.is_published
    if post.is_published and post.published_at > timezone.now():
        # Publishing a future-dated draft should make it live now, not later.
        post.published_at = timezone.now()
    post.save()
    return redirect(request.POST.get('next') or 'studio_posts')
