# Generated by Django 3.0.8 on 2020-07-24 03:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('saas', '0002_auto_20200723_0351'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='billingevent',
            options={'verbose_name_plural': 'Bills'},
        ),
        migrations.AlterModelOptions(
            name='stripeevent',
            options={'verbose_name_plural': 'Events'},
        ),
        migrations.AlterModelOptions(
            name='stripeinfo',
            options={'verbose_name_plural': 'Customers'},
        ),
        migrations.AddField(
            model_name='stripeinfo',
            name='previously_subscribed',
            field=models.BooleanField(default=False),
        ),
    ]