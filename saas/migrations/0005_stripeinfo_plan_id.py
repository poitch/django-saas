# Generated by Django 3.1.1 on 2020-11-20 20:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('saas', '0004_acquisition'),
    ]

    operations = [
        migrations.AddField(
            model_name='stripeinfo',
            name='plan_id',
            field=models.CharField(blank=True, default=None, max_length=512, null=True),
        ),
    ]