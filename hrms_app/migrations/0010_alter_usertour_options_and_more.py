# Generated by Django 4.2.16 on 2024-12-21 07:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms_app', '0009_alter_usertour_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='usertour',
            options={'managed': True, 'verbose_name': 'User Tour', 'verbose_name_plural': "Users' Tours"},
        ),
        migrations.AlterUniqueTogether(
            name='usertour',
            unique_together={('applied_by', 'slug')},
        ),
        migrations.AddIndex(
            model_name='usertour',
            index=models.Index(fields=['status'], name='tbl_user_to_status_561a11_idx'),
        ),
        migrations.AddIndex(
            model_name='usertour',
            index=models.Index(fields=['start_date'], name='tbl_user_to_start_d_6b4312_idx'),
        ),
        migrations.AddIndex(
            model_name='usertour',
            index=models.Index(fields=['end_date'], name='tbl_user_to_end_dat_5915f5_idx'),
        ),
        migrations.AddIndex(
            model_name='usertour',
            index=models.Index(fields=['slug'], name='tbl_user_to_slug_2cd5ad_idx'),
        ),
        migrations.AlterModelTable(
            name='usertour',
            table='tbl_user_tours',
        ),
    ]