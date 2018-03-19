# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-02-13 13:46
from __future__ import unicode_literals

# Django
from django.db import migrations


def migrate_laws(apps, schema_editor):
    Jurisdiction = apps.get_model('jurisdiction', 'Jurisdiction')
    Law = apps.get_model('jurisdiction', 'Law')

    for state in Jurisdiction.objects.filter(level='s'):
        try:
            law = state.law
            law.days = state.days
            law.use_business_days = state.use_business_days
            law.intro = state.intro
            law.waiver = state.waiver
            law.has_appeal = state.has_appeal
            law.requires_proxy = state.requires_proxy
            law.law_analysis = state.law_analysis
            law.save()
        except Law.DoesNotExist:
            law = Law.objects.create(
                jurisdiction=state,
                name=state.law_name or '-filler-',
                citation='-citation needed-',
                url='http://www.example.com',
                days=state.days,
                use_business_days=state.use_business_days,
                intro=state.intro,
                waiver=state.waiver,
                has_appeal=state.has_appeal,
                requires_proxy=state.requires_proxy,
                law_analysis=state.law_analysis,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('jurisdiction', '0014_auto_20180213_1337'),
    ]

    operations = [
        migrations.RunPython(migrate_laws, migrations.RunPython.noop),
    ]