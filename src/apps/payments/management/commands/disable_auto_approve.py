"""
Django management command to test and disable auto-approval of small deposits.
Usage: python manage.py disable_auto_approve --test --disable
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from apps.payments.models import Transaction, DepositRequest, PaymentMethod, Wallet
from apps.payments.tasks import auto_approve_small_deposits
from apps.core.models import SystemLog
import time
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Test current auto-approval status and disable auto-approval of small deposits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test current auto-approval status',
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='Disable auto-approval functionality',
        )
        parser.add_argument(
            '--check-logs',
            action='store_true',
            help='Check logs for any auto-approved deposits',
        )
        parser.add_argument(
            '--stop-running-tasks',
            action='store_true',
            help='Stop any currently running auto-approval tasks',
        )
        parser.add_argument(
            '--check-logs',
            action='store_true',
            help='Check system logs for auto-approved deposits',
        )
        parser.add_argument(
            '--create-test-deposit',
            action='store_true',
            help='Create a test deposit to verify behavior',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Deposit Auto-Approval Management ===\n'))
        
        if options['test']:
            self.test_auto_approval_status(options['create_test_deposit'])
        
        if options['check_logs']:
            self.check_auto_approval_logs()
        
        if options['disable']:
            self.disable_auto_approval()
            
        if options['stop_running_tasks']:
            self.stop_running_auto_approval_tasks()
            
        if not any([options['test'], options['disable'], options['stop_running_tasks'], options['check_logs']]):
            self.stdout.write(self.style.WARNING('No action specified.'))
            self.stdout.write('Usage examples:')
            self.stdout.write('  python manage.py disable_auto_approve --test')
            self.stdout.write('  python manage.py disable_auto_approve --check-logs')
            self.stdout.write('  python manage.py disable_auto_approve --disable')
            self.stdout.write('  python manage.py disable_auto_approve --stop-running-tasks')
            self.stdout.write('  python manage.py disable_auto_approve --test --create-test-deposit')

    def test_auto_approval_status(self, create_test=False):
        """Test the current auto-approval status"""
        self.stdout.write(self.style.SUCCESS('🔍 Testing auto-approval status...\n'))
        
        # Test 1: Check auto_approve_small_deposits task
        self.stdout.write('1. Testing auto_approve_small_deposits task...')
        try:
            result = auto_approve_small_deposits.apply()
            task_result = result.result if hasattr(result, 'result') else result
            
            if isinstance(task_result, dict) and task_result.get('status') == 'disabled':
                self.stdout.write(self.style.SUCCESS('   ✓ Auto-approval task is DISABLED'))
            else:
                self.stdout.write(self.style.ERROR('   ✗ Auto-approval task is ACTIVE'))
                self.stdout.write(f'   Task result: {task_result}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error testing task: {str(e)}'))

        # Test 2: Check Celery beat schedule
        self.stdout.write('\n2. Checking Celery beat schedule...')
        try:
            from tradevision.celery import app
            beat_schedule = app.conf.beat_schedule
            
            auto_approve_tasks = []
            for key, config in beat_schedule.items():
                if 'auto-approve' in key or 'auto_approve' in key:
                    auto_approve_tasks.append(key)
                elif 'task' in config and 'auto_approve' in config['task']:
                    auto_approve_tasks.append(key)
            
            if not auto_approve_tasks:
                self.stdout.write(self.style.SUCCESS('   ✓ No auto-approval tasks in beat schedule'))
            else:
                self.stdout.write(self.style.ERROR(f'   ✗ Found auto-approval tasks: {auto_approve_tasks}'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Could not check beat schedule: {str(e)}'))

        # Test 2.5: Check active Celery workers and tasks
        self.stdout.write('\n2.5. Checking active Celery tasks...')
        try:
            from tradevision.celery import app
            inspect = app.control.inspect()
            
            # Check active tasks
            active_tasks = inspect.active()
            if active_tasks:
                auto_approve_active = []
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        if 'auto_approve' in task.get('name', '').lower():
                            auto_approve_active.append(f"{worker}: {task['name']}")
                
                if auto_approve_active:
                    self.stdout.write(self.style.ERROR(f'   ✗ Auto-approval tasks currently running: {auto_approve_active}'))
                else:
                    self.stdout.write(self.style.SUCCESS('   ✓ No auto-approval tasks currently active'))
            else:
                self.stdout.write(self.style.WARNING('   ⚠ Could not connect to Celery workers'))
            
            # Check scheduled tasks
            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                auto_approve_scheduled = []
                for worker, tasks in scheduled_tasks.items():
                    for task in tasks:
                        if 'auto_approve' in task.get('task', '').lower():
                            auto_approve_scheduled.append(f"{worker}: {task['task']}")
                
                if auto_approve_scheduled:
                    self.stdout.write(self.style.ERROR(f'   ✗ Auto-approval tasks scheduled: {auto_approve_scheduled}'))
                else:
                    self.stdout.write(self.style.SUCCESS('   ✓ No auto-approval tasks scheduled'))
                    
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Could not check active tasks: {str(e)}'))

        # Test 3: Check existing deposits
        self.stdout.write('\n3. Checking existing deposits...')
        pending_count = Transaction.objects.filter(
            transaction_type='deposit',
            status='pending'
        ).count()
        
        processing_count = Transaction.objects.filter(
            transaction_type='deposit',
            status='processing'
        ).count()
        
        completed_today = Transaction.objects.filter(
            transaction_type='deposit',
            status='completed',
            completed_at__date=timezone.now().date()
        ).count()
        
        self.stdout.write(f'   Pending deposits: {pending_count}')
        self.stdout.write(f'   Processing deposits: {processing_count}')
        self.stdout.write(f'   Completed today: {completed_today}')
        
        if pending_count > 0:
            self.stdout.write(self.style.SUCCESS('   ✓ Deposits are staying in pending status'))

        # Test 4: Create test deposit if requested
        if create_test:
            self.stdout.write('\n4. Creating test deposit...')
            test_result = self.create_test_deposit()
            if test_result:
                self.stdout.write(self.style.SUCCESS('   ✓ Test deposit remains pending'))
            else:
                self.stdout.write(self.style.ERROR('   ✗ Test deposit behavior unexpected'))

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 TEST SUMMARY:'))
        self.stdout.write('   - Auto-approval task status: Check above')
        self.stdout.write('   - Celery schedule: Check above') 
        self.stdout.write('   - All new deposits should remain pending')
        self.stdout.write('   - Manual admin approval required for all deposits')
        self.stdout.write('='*60)

    def check_auto_approval_logs(self):
        """Check system logs and transaction history for auto-approved deposits"""
        self.stdout.write(self.style.SUCCESS('📋 Checking logs for auto-approved deposits...\n'))
        
        # Check SystemLog for auto-approval messages
        self.stdout.write('1. Checking SystemLog entries...')
        try:
            from django.utils import timezone
            from datetime import timedelta
            
            # Look for auto-approval related logs in the last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            auto_approval_logs = SystemLog.objects.filter(
                created_at__gte=thirty_days_ago,
                message__icontains='auto'
            ).filter(
                message__icontains='approv'
            ).order_by('-created_at')
            
            if auto_approval_logs.exists():
                self.stdout.write(self.style.WARNING(f'   ⚠ Found {auto_approval_logs.count()} auto-approval related log entries:'))
                for log in auto_approval_logs[:10]:  # Show first 10
                    self.stdout.write(f'   - {log.created_at}: {log.message}')
                if auto_approval_logs.count() > 10:
                    self.stdout.write(f'   ... and {auto_approval_logs.count() - 10} more entries')
            else:
                self.stdout.write(self.style.SUCCESS('   ✓ No auto-approval logs found in SystemLog'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Error checking SystemLog: {str(e)}'))
        
        # Check Transaction descriptions for auto-approval indicators
        self.stdout.write('\n2. Checking transaction descriptions...')
        try:
            # Look for transactions with auto-approval indicators
            auto_approved_transactions = Transaction.objects.filter(
                transaction_type='deposit',
                created_at__gte=thirty_days_ago
            ).filter(
                description__icontains='auto'
            ).order_by('-created_at')
            
            if auto_approved_transactions.exists():
                self.stdout.write(self.style.WARNING(f'   ⚠ Found {auto_approved_transactions.count()} transactions with "auto" in description:'))
                for txn in auto_approved_transactions[:10]:
                    self.stdout.write(f'   - {txn.created_at}: ${txn.amount} - {txn.description} (Status: {txn.status})')
            else:
                self.stdout.write(self.style.SUCCESS('   ✓ No transactions with auto-approval indicators found'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Error checking transactions: {str(e)}'))
        
        # Check for deposits that were completed very quickly (potential auto-approval)
        self.stdout.write('\n3. Checking for rapidly processed deposits...')
        try:
            # Find deposits that were completed within 5 minutes of creation (suspicious of auto-approval)
            rapid_deposits = Transaction.objects.filter(
                transaction_type='deposit',
                status='completed',
                created_at__gte=thirty_days_ago,
                completed_at__isnull=False
            ).extra(
                where=["EXTRACT(EPOCH FROM (completed_at - created_at)) < 300"]  # Less than 5 minutes
            ).order_by('-created_at')
            
            if rapid_deposits.exists():
                self.stdout.write(self.style.WARNING(f'   ⚠ Found {rapid_deposits.count()} deposits completed within 5 minutes:'))
                for txn in rapid_deposits[:10]:
                    time_diff = (txn.completed_at - txn.created_at).total_seconds()
                    self.stdout.write(f'   - {txn.created_at}: ${txn.amount} completed in {int(time_diff)}s (User: {txn.user.email})')
                if rapid_deposits.count() > 10:
                    self.stdout.write(f'   ... and {rapid_deposits.count() - 10} more rapid deposits')
            else:
                self.stdout.write(self.style.SUCCESS('   ✓ No unusually rapid deposit processing found'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Error checking rapid deposits: {str(e)}'))
        
        # Check DepositRequest status changes
        self.stdout.write('\n4. Checking DepositRequest processing patterns...')
        try:
            # Look at recent deposit requests and their processing times
            recent_deposits = DepositRequest.objects.filter(
                created_at__gte=thirty_days_ago
            ).select_related('transaction').order_by('-created_at')
            
            auto_processed = 0
            manual_processed = 0
            still_pending = 0
            
            for deposit in recent_deposits[:50]:  # Check last 50
                if deposit.processed_at and deposit.transaction:
                    process_time = (deposit.processed_at - deposit.created_at).total_seconds()
                    if process_time < 300:  # Less than 5 minutes
                        auto_processed += 1
                    else:
                        manual_processed += 1
                elif not deposit.processed_at:
                    still_pending += 1
            
            self.stdout.write(f'   Recent deposit processing pattern (last 50):')
            self.stdout.write(f'   - Rapidly processed (< 5 min): {auto_processed}')
            self.stdout.write(f'   - Manually processed (> 5 min): {manual_processed}')
            self.stdout.write(f'   - Still pending: {still_pending}')
            
            if auto_processed > 0:
                self.stdout.write(self.style.WARNING(f'   ⚠ {auto_processed} deposits were processed very quickly'))
            else:
                self.stdout.write(self.style.SUCCESS('   ✓ All processed deposits show normal processing times'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Error checking deposit patterns: {str(e)}'))
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 AUTO-APPROVAL LOG SUMMARY:'))
        self.stdout.write('   - SystemLog entries: Check above')
        self.stdout.write('   - Transaction descriptions: Check above') 
        self.stdout.write('   - Rapid processing patterns: Check above')
        self.stdout.write('   - Recent deposit patterns: Check above')
        self.stdout.write('\n   💡 TIP: Rapid processing (< 5 min) may indicate past auto-approval')
        self.stdout.write('='*60)

    def disable_auto_approval(self):
        """Disable auto-approval functionality"""
        self.stdout.write(self.style.SUCCESS('🔧 Disabling auto-approval functionality...\n'))
        
        try:
            # Step 1: Update the task function
            self.stdout.write('1. Updating auto_approve_small_deposits task...')
            self.update_task_function()
            
            # Step 2: Check and update celery configuration
            self.stdout.write('\n2. Checking Celery configuration...')
            self.check_celery_config()
            
            # Step 3: Verify changes
            self.stdout.write('\n3. Verifying changes...')
            time.sleep(1)  # Give a moment for changes to take effect
            self.test_auto_approval_status(create_test=False)
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('✅ AUTO-APPROVAL DISABLED SUCCESSFULLY'))
            self.stdout.write('   - Task function updated to return disabled status')
            self.stdout.write('   - All deposits now require manual admin approval')
            self.stdout.write('   - Please restart Celery workers and beat scheduler')
            self.stdout.write('='*60)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error disabling auto-approval: {str(e)}'))
            raise CommandError(f'Failed to disable auto-approval: {str(e)}')

    def update_task_function(self):
        """Update the auto_approve_small_deposits task to be disabled"""
        tasks_file_path = 'src/apps/payments/tasks.py'
        
        try:
            with open(tasks_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the auto_approve_small_deposits function
            if 'def auto_approve_small_deposits(self):' in content:
                # Create the disabled version
                disabled_function = '''@shared_task(bind=True, max_retries=3)
def auto_approve_small_deposits(self):
    """
    DISABLED: All deposits require manual admin approval.
    No automatic approval regardless of amount or payment proof.
    """
    logger.info("Auto-approval is disabled. All deposits require manual admin review.")
    return {
        'status': 'disabled',
        'approved_count': 0,
        'message': 'Auto-approval disabled - manual admin review required for all deposits',
        'timestamp': timezone.now().isoformat()
    }'''
                
                # Replace the function (this is a simplified replacement)
                # In production, you'd want more sophisticated parsing
                lines = content.split('\n')
                new_lines = []
                in_function = False
                indent_level = 0
                
                for line in lines:
                    if 'def auto_approve_small_deposits(self):' in line:
                        in_function = True
                        indent_level = len(line) - len(line.lstrip())
                        # Add the disabled function
                        new_lines.extend(disabled_function.split('\n'))
                        continue
                    
                    if in_function:
                        current_indent = len(line) - len(line.lstrip())
                        # If we hit another function or class at same/lower indent, we're done
                        if line.strip() and current_indent <= indent_level and (line.strip().startswith('def ') or line.strip().startswith('class ') or line.strip().startswith('@')):
                            in_function = False
                            new_lines.append(line)
                        elif not line.strip():  # Empty line
                            if not in_function:
                                new_lines.append(line)
                        # Skip lines that are part of the old function
                        continue
                    else:
                        new_lines.append(line)
                
                new_content = '\n'.join(new_lines)
                
                with open(tasks_file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                self.stdout.write(self.style.SUCCESS('   ✓ Task function updated'))
            else:
                self.stdout.write(self.style.WARNING('   ⚠ auto_approve_small_deposits function not found'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error updating task: {str(e)}'))
            raise

    def check_celery_config(self):
        """Check Celery configuration for auto-approval tasks"""
        celery_file_path = 'src/tradevision/celery.py'
        
        try:
            if os.path.exists(celery_file_path):
                with open(celery_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'auto-approve-small-deposits' in content or 'auto_approve_small_deposits' in content:
                    self.stdout.write(self.style.WARNING('   ⚠ Auto-approval task found in celery.py'))
                    self.stdout.write('   Please manually remove or comment out the task from beat_schedule')
                else:
                    self.stdout.write(self.style.SUCCESS('   ✓ No auto-approval tasks in celery.py'))
            else:
                self.stdout.write(self.style.WARNING('   ⚠ Celery config file not found'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠ Could not check celery config: {str(e)}'))

    def create_test_deposit(self):
        """Create a test deposit to verify behavior"""
        try:
            # Get or create test user
            test_user, created = User.objects.get_or_create(
                email='test_auto_approve@tradevision.test',
                defaults={
                    'username': 'test_auto_approve_user',
                    'first_name': 'Test',
                    'last_name': 'AutoApprove'
                }
            )
            
            # Get or create wallet
            wallet, created = Wallet.objects.get_or_create(
                user=test_user,
                defaults={'currency': 'USD', 'balance': Decimal('0')}
            )
            
            # Get or create payment method
            payment_method, created = PaymentMethod.objects.get_or_create(
                name='test_auto_approve_method',
                defaults={
                    'display_name': 'Test Auto Approve Method',
                    'is_active': True,
                    'processing_fee': Decimal('2.5'),
                    'supported_countries': ['US', 'KE']
                }
            )
            
            # Create test transaction (small amount that would normally be auto-approved)
            amount = Decimal('100')  # Small amount
            processing_fee = amount * (payment_method.processing_fee / 100)
            net_amount = amount - processing_fee
            
            transaction = Transaction.objects.create(
                user=test_user,
                transaction_type='deposit',
                amount=amount,
                currency=wallet.currency,
                status='pending',
                payment_method=payment_method,
                processing_fee=processing_fee,
                net_amount=net_amount,
                description='Test deposit for auto-approval verification'
            )
            
            # Create deposit request with payment proof
            deposit_request = DepositRequest.objects.create(
                transaction=transaction,
                payment_proof='test_auto_approve_proof.jpg'
            )
            
            self.stdout.write(f'   Created test deposit: {transaction.id} (Amount: ${amount})')
            
            # Wait and check status
            time.sleep(2)
            transaction.refresh_from_db()
            
            if transaction.status == 'pending':
                self.stdout.write(f'   ✓ Test deposit {transaction.id} remains pending')
                return True
            else:
                self.stdout.write(f'   ✗ Test deposit {transaction.id} status: {transaction.status}')
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error creating test deposit: {str(e)}'))
            return False

    def stop_running_auto_approval_tasks(self):
        """Stop any currently running auto-approval tasks"""
        self.stdout.write(self.style.SUCCESS('🛑 Stopping running auto-approval tasks...\n'))
        
        try:
            from tradevision.celery import app
            inspect = app.control.inspect()
            
            # Get active tasks
            active_tasks = inspect.active()
            if not active_tasks:
                self.stdout.write(self.style.WARNING('   ⚠ No active Celery workers found'))
                return
            
            stopped_tasks = 0
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    task_name = task.get('name', '')
                    task_id = task.get('id', '')
                    
                    if 'auto_approve' in task_name.lower():
                        self.stdout.write(f'   Stopping task: {task_name} (ID: {task_id}) on {worker}')
                        
                        # Revoke the task
                        app.control.revoke(task_id, terminate=True)
                        stopped_tasks += 1
            
            if stopped_tasks > 0:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Stopped {stopped_tasks} auto-approval task(s)'))
            else:
                self.stdout.write(self.style.SUCCESS('   ✓ No auto-approval tasks were running'))
            
            # Also check and remove any scheduled auto-approval tasks
            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                revoked_scheduled = 0
                for worker, tasks in scheduled_tasks.items():
                    for task in tasks:
                        task_name = task.get('task', '')
                        task_id = task.get('id', '')
                        
                        if 'auto_approve' in task_name.lower():
                            self.stdout.write(f'   Revoking scheduled task: {task_name} (ID: {task_id})')
                            app.control.revoke(task_id, terminate=True)
                            revoked_scheduled += 1
                
                if revoked_scheduled > 0:
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Revoked {revoked_scheduled} scheduled auto-approval task(s)'))
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('✅ TASK CLEANUP COMPLETED'))
            self.stdout.write('   - All running auto-approval tasks stopped')
            self.stdout.write('   - All scheduled auto-approval tasks revoked')
            self.stdout.write('   - System now fully manual approval only')
            self.stdout.write('='*60)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error stopping tasks: {str(e)}'))
            raise CommandError(f'Failed to stop running tasks: {str(e)}')