from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timeoff", "0003_usercarryoveroverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="dayoffrequest",
            name="revoke_requested",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="dayoffrequest",
            name="revoke_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
