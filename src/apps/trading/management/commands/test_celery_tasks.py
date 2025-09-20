# apps/trading/management/commands/test_celery_tasks.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import time
import json

from apps.trading.tasks import (
    process_completed_trades, auto_initiate_daily_trades,
    initiate_manual_trade, update_wallet_balances
)
from apps.trading.models import Investment, Trade
from apps.core.models import SystemLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Test Celery task execution and diagnose issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-simple',
            action='store_true',
            help='Test simple tasks first',
        )
        
        parser.add_argument(
            '--test-manual-trade',
            action='store_true',
            help='Test manual trade initiation specifically',
        )
        
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout for task completion in seconds (default: 30)',
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed task information',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.timeout = options['timeout']
        
        self.stdout.write(
            self.style.SUCCESS('🧪 Celery Task Testing & Diagnostics\n')
        )
        
        if options['test_simple']:
            self.test_simple_tasks()
        elif options['test_manual_trade']:
            self.test_manual_trade_specifically()
        else:
            # Run comprehensive test
            self.test_worker_communication()
            self.test_simple_tasks()
            self.test_manual_trade_specifically()

    def test_worker_communication(self):
        """Test basic worker communication"""
        self.stdout.write('🔄 Testing Worker Communication...')
        
        try:
            from celery import current_app
            
            # Test ping
            inspect = current_app.control.inspect()
            ping_result = inspect.ping()
            
            if ping_result:
                self.stdout.write(f'✅ Worker ping successful: {len(ping_result)} workers responded')
                if self.verbose:
                    for worker, response in ping_result.items():
                        self.stdout.write(f'   • {worker}: {response}')
            else:
                self.stdout.write('❌ No workers responded to ping')
                return False
                
            # Check worker stats
            stats = inspect.stats()
            if stats:
                self.stdout.write(f'✅ Worker stats available: {len(stats)} workers')
                if self.verbose:
                    for worker, worker_stats in stats.items():
                        pool = worker_stats.get('pool', {})
                        processes = pool.get('processes', 'Unknown')
                        self.stdout.write(f'   • {worker}: {processes} processes')
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Worker communication failed: {e}'))
            return False

    def test_simple_tasks(self):
        """Test simple Celery tasks"""
        self.stdout.write('\n🔧 Testing Simple Tasks...')
        
        # Test process_completed_trades (should be safe to run)
        self.stdout.write('   Testing process_completed_trades...')
        success = self._test_task_execution(
            process_completed_trades,
            task_name='process_completed_trades'
        )
        
        if not success:
            return False
        
        # Test update_wallet_balances
        self.stdout.write('   Testing update_wallet_balances...')
        success = self._test_task_execution(
            update_wallet_balances,
            task_name='update_wallet_balances'
        )
        
        if not success:
            return False
            
        # Test auto_initiate_daily_trades
        self.stdout.write('   Testing auto_initiate_daily_trades...')
        success = self._test_task_execution(
            auto_initiate_daily_trades,
            task_name='auto_initiate_daily_trades'
        )
        
        return success

    def test_manual_trade_specifically(self):
        """Test manual trade initiation with detailed diagnostics"""
        self.stdout.write('\n🎯 Testing Manual Trade Initiation...')
        
        # Find a test user and active investment
        try:
            test_user = User.objects.filter(email='test@tradevision.com').first()
            if not test_user:
                self.stdout.write('❌ Test user not found. Run: python manage.py test_trading_system --create-test-data')
                return False
                
            investment = Investment.objects.filter(
                user=test_user, 
                status='active'
            ).first()
            
            if not investment:
                self.stdout.write('❌ No active investment found for test user')
                return False
                
            self.stdout.write(f'✅ Found test data: {test_user.email}, investment: ${investment.principal_amount}')
            
            # Check for existing trades
            existing_trade = Trade.objects.filter(
                investment=investment,
                status__in=['pending', 'running']
            ).first()
            
            if existing_trade:
                self.stdout.write(f'ℹ️  Existing trade found: {existing_trade.id} (Status: {existing_trade.status})')
                # For testing, let's complete this trade first
                if existing_trade.status == 'running':
                    existing_trade.status = 'completed'
                    existing_trade.completed_at = timezone.now()
                    existing_trade.save()
                    self.stdout.write('ℹ️  Marked existing trade as completed for testing')
            
            # Now test manual trade initiation
            self.stdout.write('   Initiating manual trade...')
            
            result = self._test_task_execution(
                lambda: initiate_manual_trade(
                    investment_id=str(investment.id),
                    user_id=str(test_user.id),
                    ip_address='127.0.0.1'
                ),
                task_name='initiate_manual_trade',
                timeout=self.timeout
            )
            
            if result:
                # Check if trade was created
                new_trade = Trade.objects.filter(
                    investment=investment,
                    created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
                ).first()
                
                if new_trade:
                    self.stdout.write(f'✅ Trade created successfully: {new_trade.id}')
                    self.stdout.write(f'   Status: {new_trade.status}')
                    self.stdout.write(f'   Profit Rate: {new_trade.profit_rate}%')
                    self.stdout.write(f'   Expected Profit: ${new_trade.profit_amount}')
                else:
                    self.stdout.write('⚠️  Task completed but no trade found in database')
                    
            return result
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Manual trade test failed: {e}'))
            return False

    def _test_task_execution(self, task_func, task_name, timeout=None):
        """Test execution of a specific task"""
        if timeout is None:
            timeout = self.timeout
            
        try:
            # Submit task
            start_time = time.time()
            
            if callable(task_func):
                if hasattr(task_func, 'delay'):
                    result = task_func.delay()
                else:
                    # For lambda functions or direct calls
                    result = task_func()
                    if hasattr(result, 'delay'):
                        result = result.delay()
                    else:
                        # Direct execution result
                        execution_time = time.time() - start_time
                        self.stdout.write(f'   ✅ {task_name}: Direct execution completed in {execution_time:.2f}s')
                        if self.verbose:
                            self.stdout.write(f'      Result: {result}')
                        return True
            else:
                result = task_func.delay()
            
            task_id = result.id
            self.stdout.write(f'   📤 Task submitted: {task_id}')
            
            # Wait for completion
            wait_start = time.time()
            while not result.ready() and (time.time() - wait_start) < timeout:
                time.sleep(0.5)
                if self.verbose and int(time.time() - wait_start) % 5 == 0:
                    self.stdout.write(f'      ⏳ Waiting... ({int(time.time() - wait_start)}s)')
            
            execution_time = time.time() - start_time
            
            if result.ready():
                try:
                    task_result = result.get(timeout=1)  # Quick get since it's ready
                    
                    self.stdout.write(f'   ✅ {task_name}: Completed in {execution_time:.2f}s')
                    
                    if self.verbose:
                        if isinstance(task_result, dict):
                            status = task_result.get('status', 'unknown')
                            self.stdout.write(f'      Status: {status}')
                            
                            # Show relevant metrics
                            for key in ['processed_count', 'initiated_count', 'updated_count']:
                                if key in task_result:
                                    self.stdout.write(f'      {key.replace("_", " ").title()}: {task_result[key]}')
                        else:
                            self.stdout.write(f'      Result: {task_result}')
                    
                    return True
                    
                except Exception as e:
                    self.stdout.write(f'   ❌ {task_name}: Failed with error: {e}')
                    return False
            else:
                self.stdout.write(f'   ⏰ {task_name}: Timeout after {timeout}s')
                
                # Try to get task info
                try:
                    from celery import current_app
                    inspect = current_app.control.inspect()
                    active_tasks = inspect.active()
                    
                    task_found = False
                    for worker, tasks in active_tasks.items():
                        for task_info in tasks:
                            if task_info.get('id') == task_id:
                                task_found = True
                                self.stdout.write(f'      🔍 Task still running on worker: {worker}')
                                break
                    
                    if not task_found:
                        self.stdout.write('      🔍 Task not found in active tasks (may have failed to start)')
                        
                        # Check recent logs
                        recent_logs = SystemLog.objects.filter(
                            created_at__gte=timezone.now() - timezone.timedelta(minutes=5),
                            level__in=['ERROR', 'CRITICAL']
                        ).order_by('-created_at')[:5]
                        
                        if recent_logs:
                            self.stdout.write('      📋 Recent error logs:')
                            for log in recent_logs:
                                self.stdout.write(f'         • {log.message}')
                        
                except Exception as inspect_error:
                    self.stdout.write(f'      ⚠️  Could not inspect task: {inspect_error}')
                
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ {task_name}: Execution error: {e}'))
            return False

    def _get_task_state_info(self, result):
        """Get detailed task state information"""
        try:
            state = result.state
            info = result.info if hasattr(result, 'info') else None
            
            self.stdout.write(f'      State: {state}')
            if info:
                if isinstance(info, dict):
                    for key, value in info.items():
                        self.stdout.write(f'      {key}: {value}')
                else:
                    self.stdout.write(f'      Info: {info}')
                    
        except Exception as e:
            self.stdout.write(f'      Could not get task state: {e}')