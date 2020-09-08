# Generated by Django 3.1.1 on 2020-09-08 15:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('saas', '0003_auto_20200724_0352'),
    ]

    operations = [
        migrations.CreateModel(
            name='Acquisition',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('agent', models.CharField(blank=True, default=None, max_length=1024, null=True)),
                ('referer', models.CharField(blank=True, default=None, max_length=1024, null=True)),
                ('campaign', models.CharField(blank=True, default=None, max_length=1024, null=True)),
                ('content', models.CharField(blank=True, default=None, max_length=1024, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]