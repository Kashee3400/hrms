# Generated by Django 4.2.16 on 2024-12-28 05:46

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hrms_app', '0015_lockstatus_from_date_lockstatus_to_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leaveapplication',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'), ('pending_cancellation', 'Pending Cancellation'), ('recommended', 'Recommended'), ('not recommended', 'Not Recommended')], default='pending', help_text='Current status of the leave application.', max_length=30, verbose_name='Status'),
        ),
        migrations.CreateModel(
            name='LeaveStatusPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(blank=True, max_length=100, null=True, verbose_name='Role')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'), ('pending_cancellation', 'Pending Cancellation'), ('recommended', 'Recommended'), ('not recommended', 'Not Recommended')], max_length=30, verbose_name='Leave Status')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Leave Status Permission',
                'verbose_name_plural': 'Leave Status Permissions',
                'unique_together': {('role', 'user', 'status')},
            },
        ),
    ]
