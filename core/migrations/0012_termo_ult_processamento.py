# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2019-05-16 15:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20190516_1215'),
    ]

    operations = [
        migrations.AddField(
            model_name='termo',
            name='ult_processamento',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]