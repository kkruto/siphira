"""Nightly analytics rollup + retention prune.

Collapses raw PageView rows into one DailyStat per day, then deletes the raw
rows past the retention window. Two reasons this matters: the dashboard stays
fast without scanning a growing table, and we stop holding visitor-level data
long after it has served its purpose.

Cron: 15 0 * * *  (see scripts/crontab.siphira)
"""
import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from apps.site.models import DailyStat, PageView

RETENTION_DAYS = 90


class Command(BaseCommand):
    help = 'Roll raw page views into DailyStat and prune old raw rows.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7,
                            help='How many past days to (re)build. Default 7.')
        parser.add_argument('--retention', type=int, default=RETENTION_DAYS,
                            help=f'Delete raw views older than N days. Default {RETENTION_DAYS}.')
        parser.add_argument('--no-prune', action='store_true',
                            help='Roll up but keep all raw rows.')

    def handle(self, *args, **options):
        today = timezone.localdate()
        built = 0

        # Never roll up today — it is still accumulating, and the dashboard
        # reads today's numbers live from PageView anyway.
        for i in range(1, options['days'] + 1):
            day = today - datetime.timedelta(days=i)
            views = PageView.objects.filter(created_at__date=day)
            if not views.exists():
                continue

            top_path = (views.values('path').annotate(n=Count('id'))
                        .order_by('-n').first() or {})
            top_ref = (views.exclude(referrer_host='').values('referrer_host')
                       .annotate(n=Count('id')).order_by('-n').first() or {})

            DailyStat.objects.update_or_create(
                date=day,
                defaults={
                    'views': views.count(),
                    'visitors': views.values('visitor').distinct().count(),
                    'top_path': top_path.get('path', '')[:300],
                    'top_referrer': top_ref.get('referrer_host', '')[:150],
                },
            )
            built += 1

        self.stdout.write(self.style.SUCCESS(f'Rolled up {built} day(s).'))

        if not options['no_prune']:
            cutoff = today - datetime.timedelta(days=options['retention'])
            deleted, _ = PageView.objects.filter(created_at__date__lt=cutoff).delete()
            self.stdout.write(
                f'Pruned {deleted} raw page view(s) older than {cutoff.isoformat()}.')
