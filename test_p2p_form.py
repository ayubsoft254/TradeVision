#!/usr/bin/env python
import os
import django
import sys

# Add the project directory to Python path
sys.path.append('/path/to/your/project')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.payments.forms import P2PForm

User = get_user_model()

# Test with a Kenyan user
user = User.objects.filter(country='KE').first()
if user:
    form = P2PForm(user=user, transaction_type='deposit')
    print(f'User: {user.email} (Country: {user.country})')
    print(f'Merchants available: {form.fields["merchant"].queryset.count()}')
    print(f'Payment Methods available: {form.fields["payment_method"].queryset.count()}')
    
    print('\nAvailable merchants:')
    for m in form.fields['merchant'].queryset[:3]:
        print(f'  {m.name} - {m.country}')
    
    print('\nAvailable payment methods:')
    for pm in form.fields['payment_method'].queryset:
        print(f'  {pm.display_name}')
else:
    print('No user with country KE found')