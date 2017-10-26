# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='NpoedGradingFeatures',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', models.CharField(unique=True, max_length=255)),
                ('vertical_grading', models.BooleanField(default=False)),
                ('passing_grade', models.BooleanField(default=False)),
            ],
        ),
    ]
