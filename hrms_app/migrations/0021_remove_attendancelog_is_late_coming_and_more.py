# Generated by Django 4.2.16 on 2025-01-03 05:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms_app', '0020_remove_leavetransaction_days_applied_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='attendancelog',
            name='is_late_coming',
        ),
        migrations.RemoveField(
            model_name='personaldetails',
            name='ann_date',
        ),
        migrations.RemoveField(
            model_name='personaldetails',
            name='ctc',
        ),
        migrations.AddField(
            model_name='attendancelog',
            name='regularized',
            field=models.BooleanField(default=False, help_text='Indicate if this entry is for late coming regularization.', verbose_name='Attendance Regularized'),
        ),
        migrations.AlterField(
            model_name='leavebalanceopenings',
            name='year',
            field=models.PositiveIntegerField(default=2025, help_text='The year for which the leave balance is applicable.', verbose_name='Year'),
        ),
    ]