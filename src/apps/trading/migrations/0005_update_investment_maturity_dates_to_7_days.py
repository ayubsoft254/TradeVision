# Generated migration to update existing Investment maturity dates to 7 days from today

from django.db import migrations
from django.utils import timezone
from datetime import timedelta


def update_investment_maturity_dates(apps, schema_editor):
    """Update all existing Investment maturity_date to 7 days from today"""
    Investment = apps.get_model('trading', 'Investment')
    
    # Calculate 7 days from today
    new_maturity_date = timezone.now() + timedelta(days=7)
    
    # Update all active investments to the new maturity date
    updated_count = Investment.objects.filter(
        status='active'
    ).update(maturity_date=new_maturity_date)
    
    print(f"Updated {updated_count} active investments with maturity date: {new_maturity_date}")


def reverse_update(apps, schema_editor):
    """
    Reverse function - we cannot reliably reverse this as we don't know original dates.
    This is a data migration that intentionally doesn't have a proper reverse.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0004_alter_trade_status'),
    ]

    operations = [
        migrations.RunPython(update_investment_maturity_dates, reverse_update),
    ]
