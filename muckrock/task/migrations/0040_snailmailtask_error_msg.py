# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-10-03 18:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0039_auto_20191002_1452'),
    ]

    operations = [
        migrations.AddField(
            model_name='snailmailtask',
            name='error_msg',
            field=models.CharField(blank=True, help_text=b'The error message returned by lob', max_length=255),
        ),
    ]