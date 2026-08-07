"""NP-320 — python manage.py run_scale_benchmark --org-slug=... --profile=small"""

from django.core.management.base import BaseCommand, CommandError

from apps.ops.loadtest import PROFILES, run_benchmark
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Run NP-320 scale benchmark (small/medium/full)."

    def add_arguments(self, parser):
        parser.add_argument("--org-id", type=int, default=None)
        parser.add_argument("--org-slug", type=str, default=None)
        parser.add_argument("--profile", type=str, default="small", choices=sorted(PROFILES))
        parser.add_argument("--confirm-full", action="store_true")

    def handle(self, *args, **options):
        profile = options["profile"]
        if profile == "full" and not options["confirm_full"]:
            raise CommandError("full profil için --confirm-full gerekli")
        org = None
        if options["org_id"]:
            org = Organization.objects.filter(pk=options["org_id"]).first()
        elif options["org_slug"]:
            org = Organization.objects.filter(slug=options["org_slug"]).first()
        if org is None:
            raise CommandError("Organization bulunamadı (--org-id veya --org-slug)")
        run = run_benchmark(org, profile=profile)
        self.stdout.write(self.style.SUCCESS(f"LoadTestRun #{run.id}"))
        for k, v in (run.timings_ms or {}).items():
            self.stdout.write(f"  {k}: {v} ms")
