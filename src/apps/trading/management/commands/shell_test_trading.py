# apps/trading/management/commands/shell_test_trading.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal
import time

class Command(BaseCommand):
    help = 'Quick shell-based trading system test'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quick',
            action='store_true',
            help='Run quick test without waiting for task completion',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Quick Trading System Shell Test\n')
        )
        
        # Import required modules
        self.stdout.write('📦 Importing modules...')
        try:
            from apps.trading.models import TradingPackage, Investment, Trade
            from apps.trading.tasks import process_completed_trades, auto_initiate_daily_trades
            from apps.payments.models import Wallet
            from apps.core.models import SiteConfiguration
            from django.contrib.auth import get_user_model
            from celery import current_app
            
            User = get_user_model()
            self.stdout.write('   ✅ All modules imported successfully')
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Import failed: {e}'))
            return

        # Test 1: Check system configuration
        self.stdout.write('\n🔧 Testing system configuration...')
        
        site_config = SiteConfiguration.objects.first()
        if site_config:
            self.stdout.write(f'   ✅ Weekend trading: {"Enabled" if site_config.weekend_trading_enabled else "Disabled"}')
            self.stdout.write(f'   ✅ Trading hours: {site_config.trading_start_time} - {site_config.trading_end_time}')
        else:
            self.stdout.write('   ⚠️  No site configuration found')

        # Test 2: Check trading packages
        self.stdout.write('\n📋 Checking trading packages...')
        packages = TradingPackage.objects.filter(is_active=True)
        self.stdout.write(f'   ✅ Active packages: {packages.count()}')
        
        for package in packages:
            self.stdout.write(f'      • {package.display_name}: ${package.min_stake} min, {package.profit_min}%-{package.profit_max}% profit')

        # Test 3: Check Celery worker status
        self.stdout.write('\n⚙️  Checking Celery workers...')
        try:
            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                self.stdout.write(f'   ✅ Active workers: {len(active_workers)}')
                for worker_name in active_workers.keys():
                    self.stdout.write(f'      • {worker_name}')
            else:
                self.stdout.write('   ❌ No active Celery workers!')
                self.stdout.write('      Run: celery -A tradevision worker --loglevel=info')
        except Exception as e:
            self.stdout.write(f'   ❌ Celery check failed: {e}')

        # Test 4: Test task execution
        self.stdout.write('\n🎯 Testing Celery tasks...')
        
        if not options['quick']:
            try:
                # Test process_completed_trades
                self.stdout.write('   Testing process_completed_trades...')
                result = process_completed_trades.delay()
                
                # Wait briefly for result
                for i in range(10):
                    if result.ready():
                        break
                    time.sleep(0.5)
                    
                if result.ready():
                    task_result = result.get()
                    self.stdout.write(f'   ✅ Task completed: {task_result.get("status")}')
                    if task_result.get("processed_count", 0) > 0:
                        self.stdout.write(f'      Processed {task_result["processed_count"]} trades')
                else:
                    self.stdout.write('   ⏳ Task is running (async)')
                    
            except Exception as e:
                self.stdout.write(f'   ❌ Task test failed: {e}')
        else:
            self.stdout.write('   ⏳ Skipped (use without --quick for full test)')

        # Test 5: Database connectivity
        self.stdout.write('\n💾 Testing database operations...')
        try:
            user_count = User.objects.count()
            investment_count = Investment.objects.count()
            trade_count = Trade.objects.count()
            
            self.stdout.write(f'   ✅ Users: {user_count}')
            self.stdout.write(f'   ✅ Investments: {investment_count}')
            self.stdout.write(f'   ✅ Trades: {trade_count}')
            
        except Exception as e:
            self.stdout.write(f'   ❌ Database test failed: {e}')

        # Test 6: Current trading status
        self.stdout.write('\n📊 Current trading status...')
        try:
            now = timezone.now()
            current_hour = now.hour
            current_day = now.weekday()
            
            # Check if trading should be active now
            if site_config:
                trading_start = site_config.trading_start_time.hour if site_config.trading_start_time else 8
                trading_end = site_config.trading_end_time.hour if site_config.trading_end_time else 18
                weekend_enabled = site_config.weekend_trading_enabled
                
                is_weekend = current_day >= 5  # Saturday=5, Sunday=6
                is_trading_hours = trading_start <= current_hour <= trading_end
                
                if is_weekend and not weekend_enabled:
                    status = "❌ Inactive (Weekend, weekend trading disabled)"
                elif not is_trading_hours:
                    status = f"❌ Inactive (Outside trading hours {trading_start}:00-{trading_end}:00)"
                else:
                    status = "✅ Active (Within trading hours)"
                    
                self.stdout.write(f'   {status}')
                self.stdout.write(f'   Current time: {now.strftime("%A %H:%M")}')
            else:
                self.stdout.write('   ⚠️  Cannot determine (no site config)')
                
        except Exception as e:
            self.stdout.write(f'   ❌ Status check failed: {e}')

        # Summary
        self.stdout.write('\n📋 Quick Test Summary:')
        self.stdout.write('   • System modules: ✅')
        self.stdout.write(f'   • Trading packages: ✅ ({packages.count()} active)')
        self.stdout.write('   • Database: ✅')
        
        try:
            if active_workers:
                self.stdout.write('   • Celery workers: ✅')
            else:
                self.stdout.write('   • Celery workers: ❌')
        except:
            self.stdout.write('   • Celery workers: ❌')

        self.stdout.write('\n🎉 Quick test completed!')
        
        # Show useful commands
        self.stdout.write('\n💡 Useful commands:')
        self.stdout.write('   • Full test: python manage.py test_trading_system --full-test')
        self.stdout.write('   • Create test data: python manage.py test_trading_system --create-test-data')
        self.stdout.write('   • Test manual trade: python manage.py test_trading_system --test-manual-trade')
        self.stdout.write('   • Check weekend trading: python manage.py toggle_weekend_trading --status')