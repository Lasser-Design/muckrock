# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-03-19 20:39
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('agency', '0016_auto_20180208_1452'),
        ('tags', '0002_remove_tag_user'),
        ('foia', '0050_foiamultirequest_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='FOIAComposer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=255)),
                ('slug', models.SlugField(max_length=255)),
                ('status', models.CharField(choices=[(b'started', b'Draft'), (b'submitted', b'Processing'), (b'filed', b'Filed')], max_length=10)),
                ('requested_docs', models.TextField(blank=True)),
                ('edited_boilerplate', models.BooleanField(default=False)),
                ('datetime_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('datetime_submitted', models.DateTimeField(blank=True, null=True)),
                ('embargo', models.BooleanField(default=False)),
                ('num_org_requests', models.PositiveSmallIntegerField(default=0)),
                ('num_monthly_requests', models.PositiveSmallIntegerField(default=0)),
                ('num_reg_requests', models.PositiveSmallIntegerField(default=0)),
                ('agencies', models.ManyToManyField(related_name='composers', to='agency.Agency')),
                ('parent', models.ForeignKey(blank=True, help_text=b'The composer this was cloned from, if cloned', null=True, on_delete=django.db.models.deletion.SET_NULL, to='foia.FOIAComposer')),
                ('tags', taggit.managers.TaggableManager(blank=True, help_text='A comma-separated list of tags.', through='tags.TaggedItemBase', to='tags.Tag', verbose_name='Tags')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='composers', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterField(
            model_name='foiarequest',
            name='date_updated',
            field=models.DateField(blank=True, db_index=True, help_text=b'Date of latest communication', null=True),
        ),
        migrations.AddField(
            model_name='foiarequest',
            name='composer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='foia.FOIAComposer'),
        ),
    ]
