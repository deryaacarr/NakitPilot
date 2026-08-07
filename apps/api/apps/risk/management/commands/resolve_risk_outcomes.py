"""Management command: resolve risk prediction outcomes (NP-221)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import Organization
from apps.risk.dataset import resolve_pending_outcomes


class Command(BaseCommand):
    help = "Resolve actual_outcome on matured risk predictions (NP-221)."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=str, default=None, help="Org slug or id")

    def handle(self, *args, **options):
        org_id = None
        key = options.get("organization")
        if key:
            org = Organization.objects.filter(slug=key).first()
            if org is None and key.isdigit():
                org = Organization.objects.filter(pk=int(key)).first()
            if org is None:
                raise CommandError(f"Organization not found: {key}")
            org_id = org.id

        result = resolve_pending_outcomes(organization_id=org_id)
        self.stdout.write(self.style.SUCCESS(str(result)))
