# apps/trading/management/commands/test_simple_task.py
from django.core.management.base import BaseCommand
from apps.trading.tasks import process_completed_trades
import time

class Command(BaseCommand):
    help = 'Simple test for a single Celery task'
    
    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=30, help='Task timeout in seconds')
    
    def handle(self, *args, **options):
        timeout = options['timeout']
        
        self.stdout.write("🧪 Simple Task Test")
        self.stdout.write("=" * 40)
        
        try:
            # Send task explicitly to critical queue
            self.stdout.write("📤 Sending process_completed_trades to critical queue...")
            result = process_completed_trades.apply_async(queue='critical')
            task_id = result.id
            
            self.stdout.write(f"✅ Task submitted: {task_id}")
            
            # Wait for result
            start_time = time.time()
            while not result.ready() and (time.time() - start_time) < timeout:
                elapsed = int(time.time() - start_time)
                if elapsed % 5 == 0 and elapsed > 0:
                    self.stdout.write(f"⏳ Waiting... ({elapsed}s)")
                time.sleep(1)
            
            elapsed_total = time.time() - start_time
            
            if result.ready():
                try:
                    task_result = result.get(timeout=1)
                    self.stdout.write(f"✅ Task completed in {elapsed_total:.1f}s")
                    self.stdout.write(f"📋 Result: {task_result}")
                    return
                except Exception as e:
                    self.stdout.write(f"❌ Task failed: {e}")
                    return
            else:
                self.stdout.write(f"⏰ Task timed out after {timeout}s")
                self.stdout.write(f"🔍 Task state: {result.state}")
                return
                
        except Exception as e:
            self.stdout.write(f"❌ Error sending task: {e}")
            return