# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-03-13 12:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_auto_20211025_1800'),
    ]

    operations = [
        migrations.AddField(
            model_name='termo',
            name='last_count',
            field=models.IntegerField(default=0, verbose_name='Total de Tweets'),
        ),
    ]