# Generated by Django 3.2.9 on 2022-08-09 15:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0024_emailcommunication_message_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailopen',
            name='event',
            field=models.CharField(default='opened', max_length=10),
            preserve_default=False,
        ),
    ]