import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hrms_app", "0043_approvalmail_attendancegap"),
    ]

    operations = [
        migrations.CreateModel(
            name="AllowedUserExpiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expires_on", models.DateField(verbose_name="Allowed Until")),
                (
                    "setting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_expiries",
                        to="hrms_app.appsetting",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Allowed User Expiry",
                "verbose_name_plural": "Allowed User Expiries",
                "db_table": "tbl_allowed_user_expiry",
                "constraints": [
                    models.UniqueConstraint(fields=("setting", "user"), name="unique_allowed_user_expiry")
                ],
            },
        ),
    ]
