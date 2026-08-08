"""NP-520 — Scan an organization for financial invariant violations."""

from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import Organization
from apps.payments.invariants import audit_organization_financial_invariants


class Command(BaseCommand):
    help = "Audit payment/invoice financial invariants for an organization (NP-520)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            required=True,
            help="Organization primary key",
        )

    def handle(self, *args, **options):
        org_id = options["organization_id"]
        try:
            org = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Organization {org_id} not found") from exc

        violations = audit_organization_financial_invariants(org)
        if not violations:
            self.stdout.write(self.style.SUCCESS(f"OK — no violations for org {org_id}"))
            return

        self.stdout.write(
            self.style.ERROR(f"{len(violations)} violation(s) for org {org_id}:")
        )
        for row in violations:
            self.stdout.write(
                f"  [{row['code']}] {row['entity']}#{row['entity_id']}: {row['message']}"
            )
        raise CommandError("Financial invariant audit failed")
