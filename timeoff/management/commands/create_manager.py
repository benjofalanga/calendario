from getpass import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from timeoff.models import Country, EmployeeProfile


class Command(BaseCommand):
    help = "Create an admin/manager user for Calendario dashboard access."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Username for the new admin")
        parser.add_argument("--email", default="", help="Email for the new admin")
        parser.add_argument("--password", default="", help="Password (if omitted, interactive prompt is used)")
        parser.add_argument("--country", default="", help="Optional country code, e.g. DE or CZ")
        parser.add_argument("--allowance", type=int, default=30, help="Annual day-off allowance")

    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip()
        password = options["password"]
        country_code = options["country"].strip().upper()
        allowance = options["allowance"]

        if not username:
            raise CommandError("Username cannot be empty.")

        if allowance < 0:
            raise CommandError("Allowance cannot be negative.")

        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists.")

        if not password:
            first = getpass("Password: ")
            second = getpass("Password (again): ")
            if not first:
                raise CommandError("Password cannot be empty.")
            if first != second:
                raise CommandError("Passwords do not match.")
            password = first

        country = None
        if country_code:
            country = Country.objects.filter(code=country_code).first()
            if not country:
                valid_codes = ", ".join(Country.objects.values_list("code", flat=True))
                raise CommandError(
                    f"Country code '{country_code}' not found. Available codes: {valid_codes or 'none'}"
                )

        user = User.objects.create_user(username=username, email=email, password=password)
        profile, _ = EmployeeProfile.objects.get_or_create(user=user)
        profile.role = EmployeeProfile.ROLE_MANAGER
        profile.country = country
        profile.annual_day_off_allowance = allowance
        profile.save()

        self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' created successfully."))
