#!/usr/bin/env python3
"""
Trading Diagnosis Script
Run this to understand why trade initialization might be failing.
"""

import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from django.utils import timezone
from datetime import time
from apps.trading.models import Investment, Trade, TradingPackage
from django.contrib.auth import get_user_model

User = get_user_model()

def diagnose_trading_issues():
    print("=== Trading System Diagnosis ===\n")
    
    # 1. Check trading hours
    print("1. TRADING HOURS CHECK")
    now = timezone.now()
    current_weekday = now.weekday()
    current_time = now.time()
    
    print(f"   Current time: {now}")
    print(f"   Current weekday: {current_weekday} (Monday=0, Sunday=6)")
    print(f"   Current time of day: {current_time}")
    
    is_weekday = current_weekday < 5
    trading_start = time(8, 0)
    trading_end = time(18, 0)
    is_trading_hours = trading_start <= current_time <= trading_end
    
    print(f"   Is weekday: {is_weekday}")
    print(f"   Trading hours (8AM-6PM): {is_trading_hours}")
    print(f"   Trading allowed: {is_weekday and is_trading_hours}")
    
    # 2. Check system data
    print(f"\n2. SYSTEM DATA CHECK")
    packages = TradingPackage.objects.all()
    users = User.objects.all()
    investments = Investment.objects.all()
    trades = Trade.objects.all()
    
    print(f"   Trading packages: {packages.count()}")
    print(f"   Users: {users.count()}")
    print(f"   Total investments: {investments.count()}")
    print(f"   Total trades: {trades.count()}")
    
    # 3. Check user investments
    print(f"\n3. USER INVESTMENT STATUS")
    for user in users:
        user_investments = Investment.objects.filter(user=user, status='active')
        print(f"   User: {user.email}")
        print(f"     Active investments: {user_investments.count()}")
        
        if user_investments.exists():
            for inv in user_investments:
                active_trades = Trade.objects.filter(
                    investment=inv,
                    status__in=['pending', 'running']
                ).count()
                
                print(f"     - {inv.package.display_name}: ${inv.total_investment}")
                print(f"       Active trades: {active_trades}")
                print(f"       Can trade: {'No' if active_trades > 0 else 'Yes'}")
        else:
            print(f"     No active investments found!")
    
    # 4. Trading recommendations
    print(f"\n4. RECOMMENDATIONS")
    
    if not (is_weekday and is_trading_hours):
        print("   - Wait for trading hours: Monday-Friday, 8AM-6PM")
    
    active_investments = Investment.objects.filter(status='active')
    if not active_investments.exists():
        print("   - Create investments first using trading packages")
        print("   - Make sure you have sufficient wallet balance")
    
    available_for_trading = 0
    for inv in active_investments:
        if not Trade.objects.filter(investment=inv, status__in=['pending', 'running']).exists():
            available_for_trading += 1
    
    if available_for_trading == 0:
        print("   - Wait for existing trades to complete")
        print("   - Or create new investments for additional trading")
    else:
        print(f"   - You have {available_for_trading} investments ready for trading!")
    
    print(f"\n=== Diagnosis Complete ===")

if __name__ == "__main__":
    try:
        diagnose_trading_issues()
    except Exception as e:
        print(f"Error running diagnosis: {e}")
        import traceback
        traceback.print_exc()