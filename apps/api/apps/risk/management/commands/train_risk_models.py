"""Management command: train risk models (NP-222)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import Organization
from apps.risk.enums import DEFAULT_TARGET_LABEL
from apps.risk.training import run_training_pipeline, train_synthetic_smoke


class Command(BaseCommand):
    help = "Train and optionally publish a risk ML model for an organization (NP-222)."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=str, required=True, help="Org slug or id")
        parser.add_argument("--target-label", type=str, default=DEFAULT_TARGET_LABEL)
        parser.add_argument("--publish", action="store_true")
        parser.add_argument(
            "--synthetic",
            action="store_true",
            help="Seed synthetic labeled rows then train (dev/CI).",
        )

    def handle(self, *args, **options):
        key = options["organization"]
        org = Organization.objects.filter(slug=key).first()
        if org is None and key.isdigit():
            org = Organization.objects.filter(pk=int(key)).first()
        if org is None:
            raise CommandError(f"Organization not found: {key}")

        try:
            if options["synthetic"]:
                result = train_synthetic_smoke(org, publish=options["publish"])
            else:
                result = run_training_pipeline(
                    org,
                    target_label=options["target_label"],
                    publish=options["publish"],
                )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(str(result)))
