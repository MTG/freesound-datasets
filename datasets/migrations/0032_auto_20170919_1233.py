# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-09-19 10:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0031_auto_20170919_1201'),
    ]

    operations = [
        migrations.AddField(
            model_name='taxonomynode',
            name='negative_verification_examples_activated',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='taxonomynode',
            name='positive_verification_examples_activated',
            field=models.BooleanField(default=True),
        ),
    ]
