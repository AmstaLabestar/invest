import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update a superuser from environment variables."

    def handle(self, *args, **options):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
        phone = os.getenv('DJANGO_SUPERUSER_PHONE')

        missing = [
            name
            for name, value in {
                'DJANGO_SUPERUSER_USERNAME': username,
                'DJANGO_SUPERUSER_EMAIL': email,
                'DJANGO_SUPERUSER_PASSWORD': password,
                'DJANGO_SUPERUSER_PHONE': phone,
            }.items()
            if not value
        ]
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser creation skipped. Missing env vars: {', '.join(missing)}"
                )
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'phone_number': phone,
                'is_staff': True,
                'is_superuser': True,
                'is_platform_admin': True,
            },
        )

        user.email = email
        user.phone_number = phone
        user.is_staff = True
        user.is_superuser = True
        user.is_platform_admin = True
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Superuser {username} {action}."))
