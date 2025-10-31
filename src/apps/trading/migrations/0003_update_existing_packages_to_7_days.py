# Generated migration to update existing TradingPackage instances from 365 to 7 days

from django.db import migrations


def update_package_duration(apps, schema_editor):
    """Update all existing TradingPackage instances to use 7 days"""
    TradingPackage = apps.get_model('trading', 'TradingPackage')
    TradingPackage.objects.all().update(duration_days=7)


def reverse_update(apps, schema_editor):
    """Reverse: update back to 365 days"""
    TradingPackage = apps.get_model('trading', 'TradingPackage')
    TradingPackage.objects.all().update(duration_days=365)


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0002_alter_tradingpackage_duration_days'),
    ]

    operations = [
        migrations.RunPython(update_package_duration, reverse_update),
    ]
