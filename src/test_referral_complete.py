#!/usr/bin/env python
"""
Complete referral system test
Tests the entire flow: signup -> deposit -> commission award
"""
import os
import sys
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.accounts.models import User, Referral, UserReferralCode
from apps.payments.models import Transaction, Wallet

def cleanup_test_data():
    """Clean up any existing test data"""
    print("🧹 Cleaning up existing test data...")
    User.objects.filter(email__contains='referraltest').delete()
    print("   ✓ Test data cleaned\n")

def test_complete_referral_flow():
    """Test the complete referral flow"""
    cleanup_test_data()
    
    print("=" * 70)
    print("TESTING COMPLETE REFERRAL SYSTEM")
    print("=" * 70)
    
    # Step 1: Create referrer user
    print("\n📝 Step 1: Creating referrer user...")
    referrer = User.objects.create_user(
        email='referrer_test@example.com',
        full_name='John Referrer',
        password='testpass123'
    )
    print(f"   ✓ Created referrer: {referrer.email}")
    
    # Get referrer's code
    referrer_code = UserReferralCode.get_or_create_for_user(referrer)
    print(f"   ✓ Referrer's code: {referrer_code}")
    
    # Step 2: Create referred user using referral code
    print("\n📝 Step 2: Creating referred user with referral code...")
    referred = User.objects.create_user(
        email='referred_test@example.com',
        full_name='Jane Referred',
        password='testpass123'
    )
    print(f"   ✓ Created referred user: {referred.email}")
    
    # Manually create referral relationship (simulating signup form)
    referral = Referral.objects.create(
        referrer=referrer,
        referred=referred,
        referral_code=referrer_code
    )
    print(f"   ✓ Created referral relationship")
    
    # Step 3: Check initial state
    print("\n📝 Step 3: Checking initial state...")
    initial_commission = referral.commission_earned
    print(f"   ✓ Initial commission: ${initial_commission}")
    
    # Get or create wallets
    referrer_wallet, _ = Wallet.objects.get_or_create(user=referrer)
    referred_wallet, _ = Wallet.objects.get_or_create(user=referred)
    
    initial_referrer_balance = referrer_wallet.profit_balance
    print(f"   ✓ Referrer's initial profit balance: ${initial_referrer_balance}")
    
    # Step 4: Simulate a deposit by the referred user
    print("\n📝 Step 4: Simulating deposit by referred user...")
    deposit_amount = Decimal('100.00')
    
    deposit_transaction = Transaction.objects.create(
        user=referred,
        transaction_type='deposit',
        amount=deposit_amount,
        currency='USDT',
        status='pending',
        description='Test deposit for referral testing',
        net_amount=deposit_amount
    )
    print(f"   ✓ Created pending deposit: ${deposit_amount}")
    
    # Mark deposit as completed (this should trigger referral commission)
    deposit_transaction.status = 'completed'
    deposit_transaction.save()
    print(f"   ✓ Marked deposit as completed")
    
    # Step 5: Check if commission was awarded
    print("\n📝 Step 5: Checking if commission was awarded...")
    
    # Refresh from database
    referral.refresh_from_db()
    referrer_wallet.refresh_from_db()
    
    new_commission = referral.commission_earned
    new_referrer_balance = referrer_wallet.profit_balance
    
    commission_increase = new_commission - initial_commission
    balance_increase = new_referrer_balance - initial_referrer_balance
    
    print(f"   📊 Commission earned: ${commission_increase}")
    print(f"   📊 Wallet balance increase: ${balance_increase}")
    
    # Check if commission transaction was created
    commission_transactions = Transaction.objects.filter(
        user=referrer,
        transaction_type='referral',
        status='completed'
    )
    
    print(f"   📊 Commission transactions: {commission_transactions.count()}")
    
    if commission_transactions.exists():
        for txn in commission_transactions:
            print(f"      - {txn.description}: ${txn.amount}")
    
    # Step 6: Verify results
    print("\n📝 Step 6: Verifying results...")
    
    expected_commission = (deposit_amount * Decimal('5.0')) / Decimal('100')  # 5% commission
    
    success = True
    
    if commission_increase == expected_commission:
        print(f"   ✅ Commission amount is correct: ${commission_increase}")
    else:
        print(f"   ❌ Commission amount is INCORRECT!")
        print(f"      Expected: ${expected_commission}")
        print(f"      Actual: ${commission_increase}")
        success = False
    
    if balance_increase == expected_commission:
        print(f"   ✅ Wallet balance increase is correct: ${balance_increase}")
    else:
        print(f"   ❌ Wallet balance increase is INCORRECT!")
        print(f"      Expected: ${expected_commission}")
        print(f"      Actual: ${balance_increase}")
        success = False
    
    if commission_transactions.count() >= 1:
        print(f"   ✅ Commission transaction was created")
    else:
        print(f"   ❌ Commission transaction was NOT created")
        success = False
    
    # Step 7: Test referral dashboard view
    print("\n📝 Step 7: Testing referral dashboard data...")
    
    referrals_made = Referral.objects.filter(
        referrer=referrer,
        is_active=True
    ).count()
    
    total_earnings = Referral.objects.filter(
        referrer=referrer,
        is_active=True
    ).aggregate(total=django.db.models.Sum('commission_earned'))['total'] or 0
    
    print(f"   📊 Referrals made: {referrals_made}")
    print(f"   📊 Total earnings: ${total_earnings}")
    
    if referrals_made == 1:
        print(f"   ✅ Referral count is correct")
    else:
        print(f"   ❌ Referral count is INCORRECT (expected 1, got {referrals_made})")
        success = False
    
    if total_earnings == expected_commission:
        print(f"   ✅ Total earnings match commission")
    else:
        print(f"   ❌ Total earnings don't match commission")
        success = False
    
    # Step 8: Test multiple deposits
    print("\n📝 Step 8: Testing multiple deposits...")
    
    # Make another deposit
    deposit_2 = Transaction.objects.create(
        user=referred,
        transaction_type='deposit',
        amount=Decimal('50.00'),
        currency='USDT',
        status='completed',
        description='Second test deposit',
        net_amount=Decimal('50.00')
    )
    
    print(f"   ✓ Created second deposit: ${deposit_2.amount}")
    
    # Check commission again
    referral.refresh_from_db()
    second_commission = referral.commission_earned
    second_commission_increase = second_commission - new_commission
    expected_second_commission = (Decimal('50.00') * Decimal('5.0')) / Decimal('100')
    
    if second_commission_increase == expected_second_commission:
        print(f"   ✅ Second commission is correct: ${second_commission_increase}")
    else:
        print(f"   ❌ Second commission is INCORRECT!")
        print(f"      Expected: ${expected_second_commission}")
        print(f"      Actual: ${second_commission_increase}")
        success = False
    
    # Final Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Referrer: {referrer.email}")
    print(f"Referrer Code: {referrer_code}")
    print(f"Referred User: {referred.email}")
    print(f"Total Deposits: ${deposit_amount + Decimal('50.00')}")
    print(f"Total Commission Earned: ${second_commission}")
    print(f"Referrer Profit Balance: ${referrer_wallet.profit_balance}")
    print(f"Commission Transactions: {Transaction.objects.filter(user=referrer, transaction_type='referral').count()}")
    
    if success:
        print("\n" + "🎉 " * 10)
        print("✅ ALL TESTS PASSED! Referral system is working correctly!")
        print("🎉 " * 10)
    else:
        print("\n" + "❌ " * 10)
        print("⚠️  SOME TESTS FAILED! Please review the errors above.")
        print("❌ " * 10)
    
    return success

if __name__ == "__main__":
    try:
        import django.db.models
        success = test_complete_referral_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
