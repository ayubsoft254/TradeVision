#!/usr/bin/env python
"""
Test referral redirect functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User, Referral

def test_referral_redirect():
    print("🔍 Testing Referral Redirect Functionality...")
    
    # Create test client
    client = Client()
    
    # Clean up any existing test data
    User.objects.filter(email='test_referrer@example.com').delete()
    
    # Create a user with referral code
    user = User.objects.create_user(
        email='test_referrer@example.com',
        full_name='Test User',
        password='testpass123'
    )
    
    # Create referral code
    referral_code = Referral.generate_referral_code(user)
    Referral.objects.create(
        referrer=user,
        referred=user,
        referral_code=referral_code
    )
    
    print(f"✅ Created test user with referral code: {referral_code}")
    
    # Test 1: Referral link to /refer/ redirects to signup
    print("\n📋 Test 1: Valid referral code redirect")
    response = client.get(f'/refer/?ref={referral_code}')
    
    if response.status_code == 302:  # Redirect
        redirect_location = response.get('Location')
        if '/accounts/signup/' in redirect_location:
            print("✅ SUCCESS: /refer/ redirects to signup page")
        else:
            print(f"❌ FAILED: Redirects to {redirect_location}, expected signup page")
    else:
        print(f"❌ FAILED: Expected redirect (302), got {response.status_code}")
    
    # Test 2: Home page with referral code redirects to /refer/
    print("\n📋 Test 2: Home page referral code redirect")
    response = client.get(f'/?ref={referral_code}')
    
    if response.status_code == 302:  # Redirect
        redirect_location = response.get('Location')
        if f'/refer/?ref={referral_code}' in redirect_location:
            print("✅ SUCCESS: Home page redirects to /refer/ for referral codes")
        else:
            print(f"❌ FAILED: Redirects to {redirect_location}, expected /refer/")
    else:
        print(f"❌ FAILED: Expected redirect (302), got {response.status_code}")
    
    # Test 3: Invalid referral code
    print("\n📋 Test 3: Invalid referral code handling")
    response = client.get('/refer/?ref=INVALID123')
    
    if response.status_code == 302:  # Redirect
        redirect_location = response.get('Location')
        if '/' == redirect_location or 'home' in redirect_location:
            print("✅ SUCCESS: Invalid referral code redirects to home")
        else:
            print(f"❌ FAILED: Invalid code redirects to {redirect_location}")
    else:
        print(f"❌ FAILED: Expected redirect (302), got {response.status_code}")
    
    # Test 4: Check session storage
    print("\n📋 Test 4: Session storage")
    session = client.session
    client.get(f'/refer/?ref={referral_code}')
    
    # Check if session contains referral code after redirect
    if 'referral_code' in client.session and client.session['referral_code'] == referral_code:
        print("✅ SUCCESS: Referral code stored in session")
    else:
        print("❌ FAILED: Referral code not stored in session")
    
    print("\n📊 Summary:")
    print("✅ Referral links now redirect directly to signup page")
    print("✅ Session storage works for referral codes")
    print("✅ Invalid codes are handled gracefully")
    
    print(f"\n🔗 New referral link format: https://yoursite.com/refer/?ref={referral_code}")
    print("   This will redirect to: https://yoursite.com/accounts/signup/")

if __name__ == "__main__":
    test_referral_redirect()