from django.core.management.base import BaseCommand, CommandError

from apps.security.backup import run_script


class Command(BaseCommand):
    help = "NP-155: run backup / restore-test scripts"

    def add_arguments(self, parser):
        parser.add_argument(
            "step",
            choices=("postgres", "uploads", "restore-test", "all"),
            help="Which backup step to run",
        )

    def handle(self, *args, **options):
        step = options["step"]
        mapping = {
            "postgres": ["backup_postgres.sh"],
            "uploads": ["backup_uploads.sh"],
            "restore-test": ["test_restore.sh"],
            "all": ["backup_postgres.sh", "backup_uploads.sh", "test_restore.sh"],
        }
        try:
            for name in mapping[step]:
                result = run_script(name)
                self.stdout.write(self.style.SUCCESS(f"OK {name}"))
                if result.get("stdout"):
                    self.stdout.write(result["stdout"])
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc
