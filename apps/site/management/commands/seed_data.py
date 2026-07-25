"""Idempotent seeder — safe to run on every deploy.

Content comes from Siphira's brief. Everything seeded here is editable in
admin afterwards; re-running only fills in what is missing, so it will never
overwrite an edit she has made.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.site.models import (
    Category, NowEntry, Project, SiteSettings, Skill, SkillGroup,
)

ABOUT_BODY = """\
I've always been curious about people — about what makes them trust a product,
a brand, a person. That curiosity is what took me into merchandising and field
sales, working with beauty, skincare, and haircare brands across Nairobi and
Kiambu county.

It's the same curiosity that took me into healthcare. I trained in orthopaedic
and trauma medicine at KMTC, and worked as an administrative intern across two
county referral hospitals, serving over 200 people a day. That experience taught
me what it means to show up for people under pressure, with structure and care.

I'm ambitious — not for its own sake, but because I want to build things that
actually work for the people they're meant to serve. That's the thread running
through everything I do, from client-facing sales to the venture I'm building now.
"""

CATEGORIES = [
    ('Entrepreneurship', 'Building things, and what it actually takes.'),
    ('Technology', 'Tools, systems, and how they change the work.'),
    ('Healthcare', 'What I learned in hospitals, and what it means now.'),
    ('AI', 'Where the field is going, from where I sit.'),
    ('Design', 'How things look, and why that is never only cosmetic.'),
]

SKILL_GROUPS = [
    ('Merchandising',
     'Making a product impossible to walk past.',
     ['Visual merchandising', 'Product display', 'Shelf space optimisation',
      'Brand visibility', 'In-store promotions']),
    ('Sales & Promotion',
     'Turning interest into a decision.',
     ['Product demonstrations', 'Consultative selling', 'Objection handling',
      'Upselling', 'Daily target achievement']),
    ('Operations',
     'The unglamorous work that keeps a store honest.',
     ['Inventory management', 'Stock reconciliation', 'Daily sales reporting',
      'M-Pesa & cash handling']),
    ('Interpersonal & Languages',
     'The part that does not fit on a shelf.',
     ['Store manager relations', 'Consumer profiling', 'Team collaboration',
      'English (fluent)', 'Swahili (fluent)']),
]

NOW_ENTRIES = [
    ('building', 'Aura', 'Early days — problem definition and research.'),
    ('learning', 'The business side of building a venture', 'Finance, structure, and pricing.'),
    ('reading', 'Books on brand and consumer psychology', ''),
    ('focused', 'Getting the first version of Aura in front of real users', ''),
]


class Command(BaseCommand):
    help = 'Seed initial site content. Idempotent.'

    def handle(self, *args, **options):
        created = {'categories': 0, 'skills': 0, 'now': 0, 'projects': 0}

        # ── Site settings ────────────────────────────────────────────────────
        site = SiteSettings.load()
        if not site.about_body:
            site.about_body = ABOUT_BODY
            site.save()
            self.stdout.write('Seeded about copy.')

        # ── Categories ───────────────────────────────────────────────────────
        for i, (name, description) in enumerate(CATEGORIES):
            _, made = Category.objects.get_or_create(
                name=name, defaults={'description': description, 'order': i})
            created['categories'] += made

        # ── Skills ───────────────────────────────────────────────────────────
        for i, (name, description, items) in enumerate(SKILL_GROUPS):
            group, made = SkillGroup.objects.get_or_create(
                name=name, defaults={'description': description, 'order': i})
            created['skills'] += made
            for j, skill in enumerate(items):
                Skill.objects.get_or_create(group=group, name=skill, defaults={'order': j})

        # ── Now ──────────────────────────────────────────────────────────────
        for i, (kind, text, detail) in enumerate(NOW_ENTRIES):
            _, made = NowEntry.objects.get_or_create(
                kind=kind, text=text, defaults={'detail': detail, 'order': i})
            created['now'] += made

        # ── Projects ─────────────────────────────────────────────────────────
        _, made = Project.objects.get_or_create(
            slug='aura',
            defaults={
                'name': 'Aura',
                'tagline': 'More details coming soon.',
                'status': 'in_progress',
                'problem': 'Details coming soon.',
                'order': 0,
                'started_at': timezone.localdate(),
            },
        )
        created['projects'] += made

        summary = ', '.join(f'{v} {k}' for k, v in created.items() if v)
        self.stdout.write(self.style.SUCCESS(
            f'Seed complete. Created: {summary or "nothing new — already seeded"}.'))
