# apps/trading/management/commands/test_trading_system.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import time
from datetime import timedelta

from apps.trading.models import TradingPackage, Investment, Trade, ProfitHistory
from apps.trading.tasks import (
    process_completed_trades, auto_initiate_daily_trades, 
    initiate_manual_trade, check_investment_maturity,
    update_wallet_balances, cleanup_failed_trades
)
from apps.payments.models import Wallet, Transaction
from apps.core.models import SiteConfiguration, SystemLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Test trading system initialization and Celery tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full-test',
            action='store_true',
            help='Run comprehensive test including trade creation and processing',
        )
        
        parser.add_argument(
            '--celery-only',
            action='store_true',
            help='Test only Celery task execution without creating test data',
        )
        
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test user, package, and investment for testing',
        )
        
        parser.add_argument(
            '--test-manual-trade',
            action='store_true',
            help='Test manual trade initiation',
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data after testing',
        )
        
        parser.add_argument(
            '--user-email',
            type=str,
            default='test@tradevision.com',
            help='Email for test user (default: test@tradevision.com)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting TradeVision Trading System Test\n')
        )
        
        try:
            # Check initial system status
            self.check_system_status()
            
            if options['create_test_data']:
                self.create_test_data(options['user_email'])
                
            if options['celery_only']:
                self.test_celery_tasks()
                
            elif options['full_test']:
                self.run_full_test(options['user_email'])
                
            elif options['test_manual_trade']:
                self.test_manual_trade(options['user_email'])
                
            else:
                # Default: run basic tests
                self.run_basic_tests()
                
            if options['cleanup']:
                self.cleanup_test_data(options['user_email'])
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Test failed with error: {str(e)}')
            )
            raise CommandError(f'Testing failed: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Trading System Test Completed Successfully!')
        )

    def check_system_status(self):
        """Check basic system configuration and status"""
        self.stdout.write('📊 Checking System Status...')
        
        # Check site configuration
        site_config = SiteConfiguration.objects.first()
        if site_config:
            weekend_status = "ENABLED" if site_config.weekend_trading_enabled else "DISABLED"
            trading_hours = f"{site_config.trading_start_time} - {site_config.trading_end_time}"
            
            self.stdout.write(f'   • Weekend Trading: {weekend_status}')
            self.stdout.write(f'   • Trading Hours: {trading_hours}')
        else:
            self.stdout.write(
                self.style.WARNING('   ⚠️  No site configuration found')
            )
        
        # Check trading packages
        package_count = TradingPackage.objects.filter(is_active=True).count()
        self.stdout.write(f'   • Active Trading Packages: {package_count}')
        
        if package_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    '   ⚠️  No active trading packages found. Consider running:\n'
                    '      python manage.py add_trading_packages --default'
                )
            )
        
        # Check active investments and trades
        active_investments = Investment.objects.filter(status='active').count()
        running_trades = Trade.objects.filter(status='running').count()
        pending_trades = Trade.objects.filter(status='pending').count()
        
        self.stdout.write(f'   • Active Investments: {active_investments}')
        self.stdout.write(f'   • Running Trades: {running_trades}')
        self.stdout.write(f'   • Pending Trades: {pending_trades}')
        
        self.stdout.write('   ✅ System status check completed\n')

    def test_celery_tasks(self):
        """Test Celery task execution"""
        self.stdout.write('🔧 Testing Celery Tasks...')
        
        try:
            # Test process_completed_trades
            self.stdout.write('   Testing process_completed_trades...')
            result = process_completed_trades.delay()
            
            # Wait for task to complete (max 10 seconds)
            start_time = time.time()
            while not result.ready() and (time.time() - start_time) < 10:
                time.sleep(0.5)
            
            if result.ready():
                task_result = result.get()
                self.stdout.write(f'   ✅ process_completed_trades: {task_result.get("status", "unknown")}')
                self.stdout.write(f'      Processed: {task_result.get("processed_count", 0)} trades')
            else:
                self.stdout.write('   ⚠️  process_completed_trades: Task timeout')
            
            # Test auto_initiate_daily_trades
            self.stdout.write('   Testing auto_initiate_daily_trades...')
            result = auto_initiate_daily_trades.delay()
            
            start_time = time.time()
            while not result.ready() and (time.time() - start_time) < 10:
                time.sleep(0.5)
            
            if result.ready():
                task_result = result.get()
                self.stdout.write(f'   ✅ auto_initiate_daily_trades: {task_result.get("status", "unknown")}')
                self.stdout.write(f'      Initiated: {task_result.get("initiated_count", 0)} trades')
            else:
                self.stdout.write('   ⚠️  auto_initiate_daily_trades: Task timeout')
            
            # Test update_wallet_balances
            self.stdout.write('   Testing update_wallet_balances...')
            result = update_wallet_balances.delay()
            
            start_time = time.time()
            while not result.ready() and (time.time() - start_time) < 10:
                time.sleep(0.5)
            
            if result.ready():
                task_result = result.get()
                self.stdout.write(f'   ✅ update_wallet_balances: {task_result.get("status", "unknown")}')
                self.stdout.write(f'      Updated: {task_result.get("updated_count", 0)} wallets')
            else:
                self.stdout.write('   ⚠️  update_wallet_balances: Task timeout')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Celery test failed: {str(e)}')
            )
            raise
        
        self.stdout.write('   ✅ Celery tasks test completed\n')

    def create_test_data(self, user_email):
        """Create test data for comprehensive testing"""
        self.stdout.write('🏗️  Creating Test Data...')
        
        with transaction.atomic():
            # Create or get test user
            user, created = User.objects.get_or_create(
                email=user_email,
                defaults={
                    'first_name': 'Test',
                    'last_name': 'User',
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'   ✅ Created test user: {user_email}')
            else:
                self.stdout.write(f'   ℹ️  Using existing user: {user_email}')
            
            # Create or get wallet
            wallet, created = Wallet.objects.get_or_create(
                user=user,
                defaults={
                    'currency': 'USDT',
                    'balance': Decimal('1000.00'),
                    'profit_balance': Decimal('0.00'),
                    'locked_balance': Decimal('0.00'),
                }
            )
            
            if created:
                self.stdout.write(f'   ✅ Created wallet with $1000 balance')
            else:
                self.stdout.write(f'   ℹ️  Using existing wallet (Balance: ${wallet.balance})')
            
            # Create or get trading package
            package, created = TradingPackage.objects.get_or_create(
                name='basic',
                defaults={
                    'display_name': 'Test Basic Package',
                    'min_stake': Decimal('100.00'),
                    'profit_min': Decimal('2.50'),
                    'profit_max': Decimal('5.00'),
                    'welcome_bonus': Decimal('10.00'),
                    'duration_days': 365,
                    'is_active': True,
                }
            )
            
            if created:
                self.stdout.write(f'   ✅ Created test trading package')
            else:
                self.stdout.write(f'   ℹ️  Using existing trading package: {package.display_name}')
            
            # Create test investment if none exists
            investment, created = Investment.objects.get_or_create(
                user=user,
                package=package,
                defaults={
                    'principal_amount': Decimal('100.00'),
                    'status': 'active',
                    'maturity_date': timezone.now() + timedelta(days=365),
                }
            )
            
            if created:
                # Update wallet locked balance
                wallet.balance = Decimal('900.00')  # 1000 - 100 investment
                wallet.locked_balance = Decimal('110.00')  # 100 + 10% bonus
                wallet.save()
                
                self.stdout.write(f'   ✅ Created test investment: $100')
            else:
                self.stdout.write(f'   ℹ️  Using existing investment: ${investment.principal_amount}')
        
        self.stdout.write('   ✅ Test data creation completed\n')
        return user, package, investment

    def test_manual_trade(self, user_email):
        """Test manual trade initiation"""
        self.stdout.write('🎯 Testing Manual Trade Initiation...')
        
        try:
            # Get test user and investment
            user = User.objects.get(email=user_email)
            investment = Investment.objects.filter(user=user, status='active').first()
            
            if not investment:
                raise CommandError('No active investment found for test user')
            
            # Check if there's already a running trade
            existing_trade = Trade.objects.filter(
                investment=investment,
                status__in=['pending', 'running']
            ).first()
            
            if existing_trade:
                self.stdout.write(f'   ℹ️  Existing trade found: {existing_trade.id} (Status: {existing_trade.status})')
                return
            
            # Initiate manual trade
            self.stdout.write(f'   Initiating trade for investment: ${investment.principal_amount}')
            
            result = initiate_manual_trade.delay(
                investment_id=str(investment.id),
                user_id=str(user.id),
                ip_address='127.0.0.1'
            )
            
            # Wait for task completion
            start_time = time.time()
            while not result.ready() and (time.time() - start_time) < 15:
                time.sleep(0.5)
            
            if result.ready():
                task_result = result.get()
                
                if task_result.get('status') == 'success':
                    trade_id = task_result.get('trade_id')
                    profit_amount = task_result.get('profit_amount')
                    profit_rate = task_result.get('profit_rate')
                    
                    self.stdout.write(f'   ✅ Trade initiated successfully!')
                    self.stdout.write(f'      Trade ID: {trade_id}')
                    self.stdout.write(f'      Expected Profit: ${profit_amount} ({profit_rate}%)')
                    
                    # Get the created trade
                    trade = Trade.objects.get(id=trade_id)
                    self.stdout.write(f'      Status: {trade.status}')
                    self.stdout.write(f'      End Time: {trade.end_time}')
                    
                else:
                    error = task_result.get('error', 'Unknown error')
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ Trade initiation failed: {error}')
                    )
            else:
                self.stdout.write('   ⚠️  Manual trade task timeout')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Manual trade test failed: {str(e)}')
            )
            raise
        
        self.stdout.write('   ✅ Manual trade test completed\n')

    def run_full_test(self, user_email):
        """Run comprehensive test of the entire trading system"""
        self.stdout.write('🎯 Running Full Trading System Test...')
        
        # Create test data
        user, package, investment = self.create_test_data(user_email)
        
        # Test Celery tasks
        self.test_celery_tasks()
        
        # Test manual trade initiation
        self.test_manual_trade(user_email)
        
        # Simulate trade completion (for testing purposes)
        self.simulate_trade_completion(user_email)
        
        self.stdout.write('   ✅ Full test completed\n')

    def simulate_trade_completion(self, user_email):
        """Simulate trade completion for testing"""
        self.stdout.write('⚡ Simulating Trade Completion...')
        
        try:
            user = User.objects.get(email=user_email)
            
            # Find a running trade to complete
            running_trade = Trade.objects.filter(
                investment__user=user,
                status='running'
            ).first()
            
            if not running_trade:
                self.stdout.write('   ℹ️  No running trades found to simulate completion')
                return
            
            # Temporarily set end_time to past for testing
            original_end_time = running_trade.end_time
            running_trade.end_time = timezone.now() - timedelta(minutes=1)
            running_trade.save()
            
            self.stdout.write(f'   Simulating completion of trade: {running_trade.id}')
            
            # Run trade processing task
            result = process_completed_trades.delay()
            
            start_time = time.time()
            while not result.ready() and (time.time() - start_time) < 15:
                time.sleep(0.5)
            
            if result.ready():
                task_result = result.get()
                processed_count = task_result.get('processed_count', 0)
                
                if processed_count > 0:
                    # Refresh trade from database
                    running_trade.refresh_from_db()
                    
                    self.stdout.write(f'   ✅ Trade completed successfully!')
                    self.stdout.write(f'      Status: {running_trade.status}')
                    self.stdout.write(f'      Profit Generated: ${running_trade.profit_amount}')
                    
                    # Check if profit was added to wallet
                    wallet = user.wallet
                    wallet.refresh_from_db()
                    self.stdout.write(f'      User Profit Balance: ${wallet.profit_balance}')
                    
                    # Check profit history
                    profit_record = ProfitHistory.objects.filter(trade=running_trade).first()
                    if profit_record:
                        self.stdout.write(f'      Profit History Created: ${profit_record.amount}')
                else:
                    self.stdout.write('   ℹ️  No trades were processed (might be outside trading hours)')
            else:
                self.stdout.write('   ⚠️  Trade completion simulation timeout')
                
                # Restore original end time
                running_trade.end_time = original_end_time
                running_trade.save()
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Trade completion simulation failed: {str(e)}')
            )
            raise
        
        self.stdout.write('   ✅ Trade completion simulation completed\n')

    def run_basic_tests(self):
        """Run basic system tests without creating test data"""
        self.stdout.write('🔍 Running Basic System Tests...')
        
        # Test task availability
        try:
            from apps.trading.tasks import process_completed_trades
            self.stdout.write('   ✅ Trading tasks imported successfully')
        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Failed to import trading tasks: {e}')
            )
            return
        
        # Test Celery connection
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                worker_count = len(active_workers)
                self.stdout.write(f'   ✅ Celery workers active: {worker_count}')
                
                for worker_name, tasks in active_workers.items():
                    self.stdout.write(f'      Worker: {worker_name} ({len(tasks)} active tasks)')
            else:
                self.stdout.write(
                    self.style.WARNING('   ⚠️  No active Celery workers found')
                )
                self.stdout.write('      Make sure to run: celery -A tradevision worker --loglevel=info')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Celery connection test failed: {e}')
            )
        
        self.stdout.write('   ✅ Basic tests completed\n')

    def cleanup_test_data(self, user_email):
        """Clean up test data created during testing"""
        self.stdout.write('🧹 Cleaning Up Test Data...')
        
        try:
            with transaction.atomic():
                # Get test user
                try:
                    user = User.objects.get(email=user_email)
                    
                    # Delete trades
                    trades_deleted = Trade.objects.filter(investment__user=user).delete()[0]
                    
                    # Delete profit history
                    profits_deleted = ProfitHistory.objects.filter(user=user).delete()[0]
                    
                    # Delete transactions
                    transactions_deleted = Transaction.objects.filter(user=user).delete()[0]
                    
                    # Delete investments
                    investments_deleted = Investment.objects.filter(user=user).delete()[0]
                    
                    # Delete wallet
                    wallet_deleted = Wallet.objects.filter(user=user).delete()[0]
                    
                    # Delete system logs
                    logs_deleted = SystemLog.objects.filter(user=user).delete()[0]
                    
                    # Delete user
                    user.delete()
                    
                    self.stdout.write(f'   ✅ Deleted test user: {user_email}')
                    self.stdout.write(f'   ✅ Deleted {trades_deleted} trades')
                    self.stdout.write(f'   ✅ Deleted {profits_deleted} profit records')
                    self.stdout.write(f'   ✅ Deleted {transactions_deleted} transactions')
                    self.stdout.write(f'   ✅ Deleted {investments_deleted} investments')
                    self.stdout.write(f'   ✅ Deleted {wallet_deleted} wallet')
                    self.stdout.write(f'   ✅ Deleted {logs_deleted} system logs')
                    
                except User.DoesNotExist:
                    self.stdout.write(f'   ℹ️  Test user {user_email} not found')
                
                # Keep the test trading package for future tests
                # TradingPackage.objects.filter(name='basic').delete()
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Cleanup failed: {str(e)}')
            )
            raise
        
        self.stdout.write('   ✅ Cleanup completed\n')