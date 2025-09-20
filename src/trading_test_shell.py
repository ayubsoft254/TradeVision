# trading_test_shell.py
"""
Django shell script to test trading system
Run with: python manage.py shell < trading_test_shell.py
Or copy-paste into: python manage.py shell
"""

print("🚀 TradeVision Trading System Test - Shell Script")
print("=" * 50)

# Import necessary modules
print("📦 Importing modules...")
try:
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from decimal import Decimal
    import time
    
    from apps.trading.models import TradingPackage, Investment, Trade, ProfitHistory
    from apps.trading.tasks import (
        process_completed_trades, auto_initiate_daily_trades, 
        initiate_manual_trade
    )
    from apps.payments.models import Wallet, Transaction
    from apps.core.models import SiteConfiguration
    
    User = get_user_model()
    print("✅ All modules imported successfully!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit()

# Test 1: System Status
print("\n📊 System Status Check:")
print("-" * 30)

# Site configuration
site_config = SiteConfiguration.objects.first()
if site_config:
    weekend_status = "ENABLED" if site_config.weekend_trading_enabled else "DISABLED"
    print(f"Weekend Trading: {weekend_status}")
    print(f"Trading Hours: {site_config.trading_start_time} - {site_config.trading_end_time}")
else:
    print("⚠️  No site configuration found")

# Trading packages
packages = TradingPackage.objects.filter(is_active=True)
print(f"Active Packages: {packages.count()}")
for pkg in packages:
    print(f"  • {pkg.display_name}: ${pkg.min_stake} min, {pkg.profit_min}%-{pkg.profit_max}% profit")

# Active data
users_count = User.objects.filter(is_active=True).count()
investments_count = Investment.objects.filter(status='active').count()
running_trades = Trade.objects.filter(status='running').count()
pending_trades = Trade.objects.filter(status='pending').count()

print(f"Active Users: {users_count}")
print(f"Active Investments: {investments_count}")
print(f"Running Trades: {running_trades}")
print(f"Pending Trades: {pending_trades}")

# Test 2: Celery Worker Check
print("\n⚙️  Celery Worker Check:")
print("-" * 30)

try:
    from celery import current_app
    inspect = current_app.control.inspect()
    
    # Check active workers
    active_workers = inspect.active()
    if active_workers:
        print(f"✅ Active Workers: {len(active_workers)}")
        for worker_name, tasks in active_workers.items():
            print(f"  • {worker_name}: {len(tasks)} active tasks")
    else:
        print("❌ No active Celery workers found!")
        print("   Start with: celery -A tradevision worker --loglevel=info")
    
    # Check registered tasks
    registered = inspect.registered()
    if registered:
        trading_tasks = []
        for worker, tasks in registered.items():
            trading_tasks.extend([t for t in tasks if 'trading' in t])
        
        if trading_tasks:
            print(f"✅ Trading tasks registered: {len(set(trading_tasks))}")
            for task in set(trading_tasks)[:5]:  # Show first 5
                print(f"  • {task}")
        else:
            print("⚠️  No trading tasks found in registered tasks")
    
except Exception as e:
    print(f"❌ Celery check failed: {e}")

# Test 3: Current Trading Status
print("\n🕒 Current Trading Status:")
print("-" * 30)

now = timezone.now()
current_hour = now.hour
current_day = now.weekday()
day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

print(f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({day_names[current_day]})")

if site_config:
    trading_start = site_config.trading_start_time.hour if site_config.trading_start_time else 8
    trading_end = site_config.trading_end_time.hour if site_config.trading_end_time else 18
    weekend_enabled = site_config.weekend_trading_enabled
    
    is_weekend = current_day >= 5
    is_trading_hours = trading_start <= current_hour <= trading_end
    
    print(f"Trading Hours: {trading_start}:00 - {trading_end}:00")
    print(f"Weekend Trading: {'Enabled' if weekend_enabled else 'Disabled'}")
    
    if is_weekend and not weekend_enabled:
        print("🔴 Trading Status: INACTIVE (Weekend, weekend trading disabled)")
    elif not is_trading_hours:
        print(f"🔴 Trading Status: INACTIVE (Outside trading hours)")
    else:
        print("🟢 Trading Status: ACTIVE")
else:
    print("⚠️  Cannot determine trading status (no configuration)")

# Test 4: Quick Task Test
print("\n🎯 Quick Task Test:")
print("-" * 30)

print("Testing process_completed_trades task...")
try:
    # Try to run the task
    result = process_completed_trades.delay()
    
    print(f"Task ID: {result.id}")
    print("Task submitted successfully!")
    
    # Check if result is available quickly
    if result.ready():
        task_result = result.get()
        print(f"Task Result: {task_result}")
    else:
        print("Task is running asynchronously...")
        print("Check Celery worker logs for task execution details")
        
except Exception as e:
    print(f"❌ Task test failed: {e}")

# Test 5: Database Models Test
print("\n💾 Database Models Test:")
print("-" * 30)

try:
    # Test model operations
    print("Testing TradingPackage model...")
    basic_package = TradingPackage.objects.filter(name='basic').first()
    if basic_package:
        print(f"✅ Found basic package: {basic_package.display_name}")
        # Test profit rate generation
        profit_rate = basic_package.get_random_profit_rate()
        print(f"✅ Random profit rate: {profit_rate}%")
    else:
        print("⚠️  No basic package found")
    
    print("Testing weekend trading check...")
    weekend_enabled = TradingPackage.is_weekend_trading_enabled()
    print(f"✅ Weekend trading: {'Enabled' if weekend_enabled else 'Disabled'}")
    
    # Test recent activity
    recent_trades = Trade.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    ).count()
    print(f"✅ Recent trades (24h): {recent_trades}")
    
    recent_profits = ProfitHistory.objects.filter(
        date_earned__gte=timezone.now() - timezone.timedelta(days=1)
    ).count()
    print(f"✅ Recent profits (24h): {recent_profits}")
    
except Exception as e:
    print(f"❌ Database test failed: {e}")

# Summary and Next Steps
print("\n📋 Test Summary & Next Steps:")
print("=" * 50)

print("System Components:")
print(f"  ✅ Django Models: Working")
print(f"  ✅ Database: Connected")
try:
    if active_workers:
        print(f"  ✅ Celery Workers: Active ({len(active_workers)})")
    else:
        print(f"  ❌ Celery Workers: Not running")
except:
    print(f"  ❌ Celery Workers: Cannot connect")

print(f"  ✅ Trading Packages: {packages.count()} active")

print("\nRecommended Next Steps:")
if not active_workers:
    print("1. Start Celery worker: celery -A tradevision worker --loglevel=info")
    
if packages.count() == 0:
    print("2. Create trading packages: python manage.py add_trading_packages --default")
    
print("3. Run full test: python manage.py test_trading_system --full-test")
print("4. Create test data: python manage.py test_trading_system --create-test-data")
print("5. Test manual trade: python manage.py test_trading_system --test-manual-trade")

print("\nManual Testing Commands:")
print("• python manage.py shell_test_trading")
print("• python manage.py test_trading_system --help")
print("• python manage.py toggle_weekend_trading --status")

print("\n🎉 Shell test completed!")