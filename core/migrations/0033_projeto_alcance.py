# Generated by Django 2.2.28 on 2022-10-17 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_auto_20220924_1958'),
    ]

    operations = [
        migrations.AddField(
            model_name='projeto',
            name='alcance',
            field=models.BigIntegerField(default=0, verbose_name='Alcance Estimado'),
        ),
    ]