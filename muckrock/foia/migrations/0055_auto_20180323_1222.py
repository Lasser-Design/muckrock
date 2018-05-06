# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-03-23 16:22
from __future__ import unicode_literals

# Django
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foia', '0054_auto_20180320_0842'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='foiacomposer',
            options={'verbose_name': 'FOIA Composer'},
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='date_submitted',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='description',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='jurisdiction',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='multirequest',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='old_email',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='other_emails',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='requested_docs',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='times_viewed',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='tracker',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='updated',
        ),
        migrations.RemoveField(
            model_name='foiarequest',
            name='user',
        ),
        migrations.AlterField(
            model_name='foiacomposer',
            name='datetime_submitted',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='foiacomposer',
            name='status',
            field=models.CharField(
                choices=[(b'started', b'Draft'), (b'submitted', b'Processing'),
                         (b'filed', b'Filed')],
                default=b'started',
                max_length=10
            ),
        ),
        migrations.AlterField(
            model_name='foiacomposer',
            name='title',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='foiarequest',
            name='agency',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to='agency.Agency'
            ),
        ),
        migrations.AlterField(
            model_name='foiarequest',
            name='composer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='foias',
                to='foia.FOIAComposer'
            ),
        ),
        migrations.AlterField(
            model_name='foiarequest',
            name='datetime_done',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name=b'Date response received'
            ),
        ),
        migrations.AlterField(
            model_name='foiarequest',
            name='datetime_updated',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=b'Date of latest communication',
                null=True
            ),
        ),
    ]
