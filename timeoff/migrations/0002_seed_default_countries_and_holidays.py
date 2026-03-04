from datetime import date

from django.db import migrations


def seed_defaults(apps, schema_editor):
    Country = apps.get_model("timeoff", "Country")
    PublicHoliday = apps.get_model("timeoff", "PublicHoliday")

    germany, _ = Country.objects.get_or_create(code="DE", defaults={"name": "Germany"})
    czech, _ = Country.objects.get_or_create(code="CZ", defaults={"name": "Czech Republic"})

    germany_holidays_2026 = [
        ("New Year's Day", date(2026, 1, 1)),
        ("Good Friday", date(2026, 4, 3)),
        ("Easter Monday", date(2026, 4, 6)),
        ("Labour Day", date(2026, 5, 1)),
        ("Ascension Day", date(2026, 5, 14)),
        ("Whit Monday", date(2026, 5, 25)),
        ("German Unity Day", date(2026, 10, 3)),
        ("Christmas Day", date(2026, 12, 25)),
        ("Second Day of Christmas", date(2026, 12, 26)),
    ]

    czech_holidays_2026 = [
        ("Restoration Day of the Czech State", date(2026, 1, 1)),
        ("Good Friday", date(2026, 4, 3)),
        ("Easter Monday", date(2026, 4, 6)),
        ("Labour Day", date(2026, 5, 1)),
        ("Liberation Day", date(2026, 5, 8)),
        ("Saints Cyril and Methodius Day", date(2026, 7, 5)),
        ("Jan Hus Day", date(2026, 7, 6)),
        ("St. Wenceslas Day", date(2026, 9, 28)),
        ("Independent Czechoslovak State Day", date(2026, 10, 28)),
        ("Struggle for Freedom and Democracy Day", date(2026, 11, 17)),
        ("Christmas Eve", date(2026, 12, 24)),
        ("Christmas Day", date(2026, 12, 25)),
        ("St. Stephen's Day", date(2026, 12, 26)),
    ]

    for name, holiday_date in germany_holidays_2026:
        PublicHoliday.objects.get_or_create(country=germany, name=name, date=holiday_date)

    for name, holiday_date in czech_holidays_2026:
        PublicHoliday.objects.get_or_create(country=czech, name=name, date=holiday_date)


def remove_defaults(apps, schema_editor):
    Country = apps.get_model("timeoff", "Country")
    PublicHoliday = apps.get_model("timeoff", "PublicHoliday")

    PublicHoliday.objects.filter(country__code__in=["DE", "CZ"], date__year=2026).delete()
    Country.objects.filter(code__in=["DE", "CZ"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("timeoff", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, remove_defaults),
    ]
