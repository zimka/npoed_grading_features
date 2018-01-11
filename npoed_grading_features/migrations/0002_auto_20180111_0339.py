# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('npoed_grading_features', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoursePassingGradeUserStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', models.CharField(max_length=255)),
                ('fail_status_messages', models.TextField(verbose_name=b'Message that specifies what user has to do to pass')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='coursepassinggradeuserstatus',
            unique_together=set([('course_id', 'user')]),
        ),
    ]
