# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-03-07 18:06
from __future__ import unicode_literals

from django.db import migrations
import localflavor.us.models


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0009_auto_20171129_1253'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='address',
            options={'verbose_name_plural': 'addresses'},
        ),
        migrations.AlterModelOptions(
            name='emailaddress',
            options={'verbose_name_plural': 'email addresses'},
        ),
        migrations.AlterField(
            model_name='address',
            name='state',
            field=localflavor.us.models.USStateField(blank=True),
        ),
    ]