import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hrms_app", "0042_device_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalMail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("attendance", "Attendance"),
                            ("leave_policy", "Leave Policy"),
                            ("tour_policy", "Tour Policy"),
                        ],
                        max_length=20,
                        verbose_name="Kind",
                    ),
                ),
                ("start_date", models.DateField(verbose_name="Start Date")),
                ("end_date", models.DateField(verbose_name="End Date")),
                ("subject", models.CharField(max_length=255, verbose_name="Subject")),
                ("body", models.TextField(verbose_name="Body")),
                ("reason", models.TextField(verbose_name="Reason")),
                ("to_email", models.CharField(max_length=255, verbose_name="To")),
                ("cc_emails", models.JSONField(default=list, verbose_name="CC")),
                ("sent_at", models.DateTimeField(auto_now_add=True, verbose_name="Sent At")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_mails",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Employee",
                    ),
                ),
            ],
            options={
                "verbose_name": "Approval Mail",
                "verbose_name_plural": "Approval Mails",
                "db_table": "tbl_approval_mail",
                "ordering": ["-sent_at"],
                "indexes": [models.Index(fields=["user", "start_date"], name="idx_approval_mail_user_date")],
            },
        ),
        migrations.CreateModel(
            name="AttendanceGap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(verbose_name="Date")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("absent", "Absent"),
                            ("no_record", "No Attendance Record"),
                            ("missing_punch", "Missing Punch-out"),
                        ],
                        max_length=20,
                        verbose_name="Kind",
                    ),
                ),
                ("is_open", models.BooleanField(default=True, verbose_name="Is Open")),
                ("first_notified_on", models.DateField(blank=True, null=True, verbose_name="First Reminder")),
                ("last_day_notified_on", models.DateField(blank=True, null=True, verbose_name="Last Day Reminder")),
                ("expired_notified_on", models.DateField(blank=True, null=True, verbose_name="Expiry Notice")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                (
                    "approval_mail",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gaps",
                        to="hrms_app.approvalmail",
                        verbose_name="Approval Mail",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_gaps",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Employee",
                    ),
                ),
            ],
            options={
                "verbose_name": "Attendance Gap",
                "verbose_name_plural": "Attendance Gaps",
                "db_table": "tbl_attendance_gap",
                "ordering": ["-date"],
                "indexes": [models.Index(fields=["is_open", "date"], name="idx_attendance_gap_open_date")],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "date"), name="unique_attendance_gap_user_date")
                ],
            },
        ),
    ]
