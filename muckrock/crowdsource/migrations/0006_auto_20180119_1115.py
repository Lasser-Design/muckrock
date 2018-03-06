# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-19 11:15
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crowdsource', '0005_crowdsourceresponse_skip'),
    ]

    operations = [
        migrations.AddField(
            model_name='crowdsource',
            name='data_limit',
            field=models.PositiveSmallIntegerField(default=3, help_text=b'Number of times each data assignment will be completed (by different users) - only used if using data for this crowdsource', validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='crowdsource',
            name='user_limit',
            field=models.BooleanField(default=True, help_text=b'Is the user limited to completing this form only once? (else, it is unlimited) - only used if not using data for this crowdsource'),
        ),
    ]