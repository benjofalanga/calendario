from django.core.management.base import BaseCommand

from timeoff.models import UserCarryoverOverride


class Command(BaseCommand):
    help = "Delete legacy manual carryover override rows (carryover is now automatic)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be deleted without deleting them.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        assume_yes = options["yes"]

        count = UserCarryoverOverride.objects.count()
        if count == 0:
            self.stdout.write("No legacy carryover override rows found.")
            return

        if dry_run:
            self.stdout.write(f"Dry run: would delete {count} carryover override row(s).")
            return

        if not assume_yes:
            confirmation = input(
                f"Delete {count} carryover override row(s)? Type 'yes' to confirm: "
            ).strip().lower()
            if confirmation != "yes":
                self.stdout.write("Cancelled. No rows were deleted.")
                return

        deleted_count, _ = UserCarryoverOverride.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} carryover override row(s)."
            )
        )
