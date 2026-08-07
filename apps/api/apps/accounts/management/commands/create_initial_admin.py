"""NP-185 — create the first Django admin without embedding secrets in code."""

from __future__ import annotations

import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = (
        "NP-185: create or update the initial staff/superuser admin. "
        "Password must come from INITIAL_ADMIN_PASSWORD env or an interactive prompt — never from source."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=os.getenv("INITIAL_ADMIN_EMAIL", ""),
            help="Admin email (or set INITIAL_ADMIN_EMAIL).",
        )
        parser.add_argument(
            "--first-name",
            default=os.getenv("INITIAL_ADMIN_FIRST_NAME", "Admin"),
            help="Optional first name.",
        )
        parser.add_argument(
            "--last-name",
            default=os.getenv("INITIAL_ADMIN_LAST_NAME", ""),
            help="Optional last name.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Non-interactive: require INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD env vars.",
        )

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip().lower()
        if not email:
            if options["noinput"]:
                raise CommandError("INITIAL_ADMIN_EMAIL (or --email) is required with --noinput.")
            email = input("Admin email: ").strip().lower()
        if not email:
            raise CommandError("Email is required.")

        password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        if not password:
            if options["noinput"]:
                raise CommandError(
                    "INITIAL_ADMIN_PASSWORD env var is required with --noinput. "
                    "Do not pass passwords on the CLI."
                )
            password = getpass.getpass("Admin password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise CommandError("Passwords do not match.")
        if len(password) < 10:
            raise CommandError("Password must be at least 10 characters.")

        user = User.objects.filter(email=email).first()
        created = user is None
        if created:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=options["first_name"] or "",
                last_name=options["last_name"] or "",
            )
            self.stdout.write(self.style.SUCCESS(f"Created initial admin: {user.email}"))
        else:
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if options["first_name"]:
                user.first_name = options["first_name"]
            if options["last_name"]:
                user.last_name = options["last_name"]
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.WARNING(f"Updated existing admin: {user.email}"))

        # Never echo the password.
        self.stdout.write(f"id={user.pk} staff={user.is_staff} superuser={user.is_superuser}")
