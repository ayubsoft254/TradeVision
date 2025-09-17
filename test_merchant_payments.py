#!/usr/bin/env python
"""
Test script to verify merchant payment method functionality
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/henry/Desktop/TradeVision/src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.payments.models import P2PMerchant, PaymentMethod
from apps.payments.forms import P2PForm

User = get_user_model()

def test_merchant_payment_methods():
    print("=== Testing Merchant Payment Methods ===\n")
    
    # Check merchants and their payment methods
    merchants = P2PMerchant.objects.all()
    print(f"Total merchants: {merchants.count()}")
    
    for merchant in merchants:
        methods = merchant.payment_methods.all()
        print(f"✅ {merchant.name} ({merchant.country}): {methods.count()} methods")
        for method in methods:
            print(f"   - {method.display_name}")
        print()
    
    # Test form with a Kenyan user
    print("=== Testing P2P Form ===\n")
    user = User.objects.filter(country='KE').first()
    if user:
        print(f"Testing with user: {user.email} (Country: {user.country})")
        
        form = P2PForm(user=user, transaction_type='deposit')
        
        merchants_queryset = form.fields['merchant'].queryset
        methods_queryset = form.fields['payment_method'].queryset
        
        print(f"Available merchants: {merchants_queryset.count()}")
        for merchant in merchants_queryset:
            print(f"  - {merchant.name}")
        
        print(f"Available payment methods: {methods_queryset.count()}")
        for method in methods_queryset:
            print(f"  - {method.display_name}")
        
        # Test merchant-method compatibility
        print("\n=== Testing Merchant-Method Compatibility ===")
        for merchant in merchants_queryset:
            merchant_methods = merchant.payment_methods.all()
            print(f"{merchant.name} supports:")
            for method in merchant_methods:
                available_in_form = method in methods_queryset
                status = "✅" if available_in_form else "❌"
                print(f"  {status} {method.display_name}")
    else:
        print("No Kenyan user found for testing")

if __name__ == '__main__':
    test_merchant_payment_methods()