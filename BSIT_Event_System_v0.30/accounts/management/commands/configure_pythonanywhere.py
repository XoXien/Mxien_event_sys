"""Create private production settings for a PythonAnywhere deployment."""
import os
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management.utils import get_random_secret_key
from dotenv import dotenv_values, set_key


class Command(BaseCommand):
    help = "Configure HTTPS hosts and a persistent secret key in the project's .env file."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("domain", help="Your exact Web tab domain, without https://")

    def handle(self, *args, **options):
        domain = options["domain"].strip().lower()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", domain):
            raise CommandError("Enter a hostname such as username.pythonanywhere.com.")

        env_path = Path(settings.BASE_DIR) / ".env"
        if not env_path.exists():
            fd = os.open(env_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        env_path.chmod(0o600)
        existing = dotenv_values(env_path, interpolate=False)
        secret = os.environ.get("DJANGO_SECRET_KEY") or existing.get("DJANGO_SECRET_KEY")
        if not secret or secret.startswith("django-insecure-") or len(secret) < 50 or len(set(secret)) < 5:
            secret = get_random_secret_key()

        values = {
            "DJANGO_SECRET_KEY": secret,
            "DJANGO_ALLOWED_HOSTS": domain,
            "DJANGO_CSRF_TRUSTED_ORIGINS": f"https://{domain}",
            "PASSWORD_RESET_ORIGIN": f"https://{domain}",
            "DJANGO_DEBUG": "0",
        }
        for key, value in values.items():
            set_key(str(env_path), key, value)
        env_path.chmod(0o600)
        self.stdout.write(self.style.SUCCESS(f"Production configuration saved for https://{domain}."))
        self.stdout.write("Existing email credentials and database files were not changed.")
        self.stdout.write("Enable Force HTTPS in the PythonAnywhere Web tab and reload.")
