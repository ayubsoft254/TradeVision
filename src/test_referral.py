#!/usr/bin/env python
"""
Test script to verify referral functionality
Run this with: python manage.py shell < test_referral.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from apps.accounts.models import User, Referral
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from apps.accounts.forms import CustomSignupForm

def test_referral_functionality():
    print("🔍 Testing Referral Functionality...")
    
    # Clean up any existing test users
    User.objects.filter(email__in=['referrer@test.com', 'referred@test.com']).delete()
    
    print("\n1. Creating referrer user...")
    # Create a referrer user
    referrer = User.objects.create_user(
        email='referrer@test.com',
        full_name='Referrer User',
        password='testpass123'
    )
    
    # Generate referral code for referrer
    referral_code = Referral.generate_referral_code(referrer)
    referral_record = Referral.objects.create(
        referrer=referrer,
        referred=referrer,  # Self-referral for code storage
        referral_code=referral_code
    )
    
    print(f"✅ Referrer created with referral code: {referral_code}")
    
    print("\n2. Testing referral code in session...")
    # Create a mock request with session containing referral code
    factory = RequestFactory()
    request = factory.post('/accounts/signup/', {
        'email': 'referred@test.com',
        'full_name': 'Referred User',
        'password1': 'testpass123',
        'password2': 'testpass123',
        'phone_number': '+254700000001',
        'country': 'KE',
        'referral_code': ''  # Empty, should use session
    })
    
    # Add session middleware
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    
    # Set referral code in session
    request.session['referral_code'] = referral_code
    
    print(f"✅ Session contains referral code: {request.session.get('referral_code')}")
    
    print("\n3. Testing form with session referral code...")
    # Test form with request (simulating allauth behavior)
    form = CustomSignupForm(request.POST, request=request)
    
    if form.is_valid():
        print("✅ Form is valid")
        
        # Save user using form
        user = form.save(request)
        print(f"✅ User created: {user.email}")
        
        # Check if referral was created
        referral_created = Referral.objects.filter(
            referrer=referrer,
            referred=user
        ).exists()
        
        if referral_created:
            print("✅ SUCCESS: Referral relationship created!")
            
            # Check if session was cleared
            session_cleared = 'referral_code' not in request.session
            if session_cleared:
                print("✅ SUCCESS: Referral code cleared from session")
            else:
                print("⚠️  WARNING: Referral code still in session")
                
        else:
            print("❌ FAILED: Referral relationship NOT created")
            
        # Print referral stats
        total_referrals = Referral.objects.filter(referrer=referrer).exclude(referred=referrer).count()
        print(f"📊 Total referrals for {referrer.email}: {total_referrals}")
        
    else:
        print("❌ Form validation failed:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
    
    print("\n4. Testing direct referral code entry...")
    # Test with referral code entered directly in form
    request2 = factory.post('/accounts/signup/', {
        'email': 'referred2@test.com',
        'full_name': 'Referred User 2',
        'password1': 'testpass123',
        'password2': 'testpass123',
        'phone_number': '+254700000002',
        'country': 'KE',
        'referral_code': referral_code  # Direct entry
    })
    
    middleware.process_request(request2)
    request2.session.save()
    
    form2 = CustomSignupForm(request2.POST, request=request2)
    
    if form2.is_valid():
        user2 = form2.save(request2)
        print(f"✅ User 2 created: {user2.email}")
        
        referral_created2 = Referral.objects.filter(
            referrer=referrer,
            referred=user2
        ).exists()
        
        if referral_created2:
            print("✅ SUCCESS: Direct referral code entry works!")
        else:
            print("❌ FAILED: Direct referral code entry failed")
    else:
        print("❌ Form 2 validation failed:")
        for field, errors in form2.errors.items():
            print(f"  {field}: {errors}")
    
    # Final stats
    print(f"\n📊 Final Statistics:")
    print(f"Total users: {User.objects.count()}")
    print(f"Total referrals: {Referral.objects.count()}")
    print(f"Active referrals for {referrer.email}: {Referral.objects.filter(referrer=referrer).exclude(referred=referrer).count()}")
    
    # List all referrals
    print(f"\n📋 All Referrals:")
    for ref in Referral.objects.all():
        ref_type = "Self-referral (code storage)" if ref.referrer == ref.referred else "Active referral"
        print(f"  {ref.referrer.email} -> {ref.referred.email} ({ref_type}) [Code: {ref.referral_code}]")

if __name__ == "__main__":
    test_referral_functionality()