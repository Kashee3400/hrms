# Generated by Django 4.2.16 on 2025-06-02 07:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms_app', '0029_alter_attendancelog_regularized_backend'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaveapplication',
            name='is_leave_deducted',
            field=models.BooleanField(default=False),
        ),
    ]
