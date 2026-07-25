"""Create or reset the admin superuser from environment variables.

Idempotent so it can run on every deploy: if the user exists the password is
left alone unless ADMIN_PASSWORD_RESET=1 is set.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the admin superuser if it does not already exist.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('ADMIN_USERNAME', 'siphira')
        email = os.environ.get('ADMIN_EMAIL', 'siphirawanjiku0@gmail.com')
        password = os.environ.get('ADMIN_PASSWORD', '')

        user = User.objects.filter(username=username).first()
        if user:
            if os.environ.get('ADMIN_PASSWORD_RESET') == '1' and password:
                user.set_password(password)
                user.is_staff = user.is_superuser = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Reset password for "{username}".'))
            else:
                self.stdout.write(f'User "{username}" already exists — untouched.')
            return

        if not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_PASSWORD not set — skipping superuser creation. '
                'Run: python manage.py createsuperuser'))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f'Created superuser "{username}".'))
