# apps/trading/management/commands/check_celery.py
from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Check Celery configuration and worker status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-worker',
            action='store_true',
            help='Show command to start Celery worker',
        )
        
        parser.add_argument(
            '--check-redis',
            action='store_true', 
            help='Check Redis connection (if using Redis as broker)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 Celery Configuration Check')
        )
        self.stdout.write('=' * 50)
        
        # Check Celery app configuration
        self.check_celery_config()
        
        # Check broker connection
        self.check_broker_connection()
        
        # Check workers
        self.check_workers()
        
        # Check registered tasks
        self.check_registered_tasks()
        
        if options['check_redis']:
            self.check_redis_connection()
            
        if options['start_worker']:
            self.show_worker_commands()
            
        # Show diagnostics summary
        self.show_diagnostics_summary()

    def check_celery_config(self):
        """Check Celery configuration"""
        self.stdout.write('\n📋 Celery Configuration:')
        self.stdout.write('-' * 30)
        
        try:
            from tradevision.celery import app as celery_app
            
            # Check if Celery app exists
            self.stdout.write(f'✅ Celery app found: {celery_app.main}')
            
            # Check broker URL
            broker_url = getattr(settings, 'CELERY_BROKER_URL', 'Not configured')
            self.stdout.write(f'📡 Broker URL: {broker_url}')
            
            # Check result backend
            result_backend = getattr(settings, 'CELERY_RESULT_BACKEND', 'Not configured')
            self.stdout.write(f'💾 Result Backend: {result_backend}')
            
            # Check timezone
            timezone = getattr(settings, 'CELERY_TIMEZONE', settings.TIME_ZONE)
            self.stdout.write(f'🌍 Timezone: {timezone}')
            
        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Celery app import failed: {e}')
            )
            self.stdout.write('   Check tradevision/celery.py configuration')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Celery configuration error: {e}')
            )

    def check_broker_connection(self):
        """Check broker connection"""
        self.stdout.write('\n🔗 Broker Connection:')
        self.stdout.write('-' * 30)
        
        try:
            from celery import current_app
            
            # Try to connect to broker
            conn = current_app.connection()
            conn.ensure_connection(max_retries=3)
            
            self.stdout.write('✅ Broker connection successful')
            
            # Get broker info
            broker_url = current_app.conf.broker_url
            if broker_url.startswith('redis://'):
                self.stdout.write('📡 Broker type: Redis')
            elif broker_url.startswith('amqp://'):
                self.stdout.write('📡 Broker type: RabbitMQ')
            else:
                self.stdout.write(f'📡 Broker type: {broker_url.split("://")[0]}')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Broker connection failed: {e}')
            )
            self.stdout.write('   Make sure your message broker is running')

    def check_workers(self):
        """Check active workers"""
        self.stdout.write('\n👷 Worker Status:')
        self.stdout.write('-' * 30)
        
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            # Check active workers
            active_workers = inspect.active()
            if active_workers:
                self.stdout.write(f'✅ Active workers: {len(active_workers)}')
                for worker_name, tasks in active_workers.items():
                    self.stdout.write(f'   • {worker_name}: {len(tasks)} active tasks')
                    
                # Check worker stats
                stats = inspect.stats()
                if stats:
                    for worker_name, worker_stats in stats.items():
                        pool_info = worker_stats.get('pool', {})
                        processes = pool_info.get('processes', 'Unknown')
                        self.stdout.write(f'   • {worker_name}: {processes} processes')
                        
            else:
                self.stdout.write('❌ No active workers found')
                self.stdout.write('   Start workers with: celery -A tradevision worker --loglevel=info')
                
            # Check registered workers
            registered = inspect.registered()
            if registered:
                task_count = sum(len(tasks) for tasks in registered.values())
                self.stdout.write(f'📋 Registered tasks: {task_count}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Worker check failed: {e}')
            )

    def check_registered_tasks(self):
        """Check registered tasks"""
        self.stdout.write('\n📋 Registered Tasks:')
        self.stdout.write('-' * 30)
        
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            registered = inspect.registered()
            if registered:
                # Collect all unique tasks
                all_tasks = set()
                for worker_tasks in registered.values():
                    all_tasks.update(worker_tasks)
                
                # Filter trading tasks
                trading_tasks = [task for task in all_tasks if 'trading' in task.lower()]
                
                self.stdout.write(f'📊 Total tasks: {len(all_tasks)}')
                self.stdout.write(f'🎯 Trading tasks: {len(trading_tasks)}')
                
                if trading_tasks:
                    self.stdout.write('\n🎯 Trading Tasks:')
                    for task in sorted(trading_tasks):
                        self.stdout.write(f'   • {task}')
                else:
                    self.stdout.write('   ⚠️  No trading tasks found')
                    
            else:
                self.stdout.write('❌ No registered tasks found (no workers running)')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Task registration check failed: {e}')
            )

    def check_redis_connection(self):
        """Check Redis connection if using Redis"""
        self.stdout.write('\n🔴 Redis Connection Check:')
        self.stdout.write('-' * 30)
        
        try:
            import redis
            from django.conf import settings
            
            # Try to connect to Redis
            broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
            
            if 'redis' in broker_url:
                # Parse Redis URL
                if broker_url.startswith('redis://'):
                    redis_client = redis.from_url(broker_url)
                else:
                    redis_client = redis.Redis(host='localhost', port=6379, db=0)
                
                # Test connection
                response = redis_client.ping()
                if response:
                    self.stdout.write('✅ Redis connection successful')
                    
                    # Get Redis info
                    info = redis_client.info()
                    redis_version = info.get('redis_version', 'Unknown')
                    connected_clients = info.get('connected_clients', 0)
                    
                    self.stdout.write(f'   Version: {redis_version}')
                    self.stdout.write(f'   Connected clients: {connected_clients}')
                else:
                    self.stdout.write('❌ Redis ping failed')
                    
            else:
                self.stdout.write('ℹ️  Not using Redis as broker')
                
        except ImportError:
            self.stdout.write('⚠️  Redis package not installed')
            self.stdout.write('   Install with: pip install redis')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Redis connection failed: {e}')
            )
            self.stdout.write('   Make sure Redis server is running')

    def show_worker_commands(self):
        """Show commands to start workers"""
        self.stdout.write('\n🚀 Worker Start Commands:')
        self.stdout.write('-' * 30)
        
        # Detect OS and show appropriate commands
        if os.name == 'nt':  # Windows
            self.stdout.write('Windows Commands:')
            self.stdout.write('   # Start single worker')
            self.stdout.write('   celery -A tradevision worker --loglevel=info --pool=solo')
            self.stdout.write('')
            self.stdout.write('   # Start multiple workers (use separate terminals)')
            self.stdout.write('   celery -A tradevision worker --loglevel=info --concurrency=2')
            self.stdout.write('')
            self.stdout.write('   # Start beat scheduler (for periodic tasks)')
            self.stdout.write('   celery -A tradevision beat --loglevel=info')
        else:  # Linux/Mac
            self.stdout.write('Linux/Mac Commands:')
            self.stdout.write('   # Start single worker')
            self.stdout.write('   celery -A tradevision worker --loglevel=info')
            self.stdout.write('')
            self.stdout.write('   # Start worker with specific concurrency')
            self.stdout.write('   celery -A tradevision worker --loglevel=info --concurrency=4')
            self.stdout.write('')
            self.stdout.write('   # Start beat scheduler')
            self.stdout.write('   celery -A tradevision beat --loglevel=info')
            self.stdout.write('')
            self.stdout.write('   # Start both worker and beat')
            self.stdout.write('   celery -A tradevision worker --beat --loglevel=info')

    def show_diagnostics_summary(self):
        """Show diagnostics summary and recommendations"""
        self.stdout.write('\n📊 Diagnostics Summary:')
        self.stdout.write('=' * 50)
        
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                self.stdout.write('✅ System Status: READY')
                self.stdout.write(f'   Workers: {len(active_workers)} active')
                self.stdout.write('   Recommendation: Run trading tests')
                
                self.stdout.write('\n💡 Next Steps:')
                self.stdout.write('   1. python manage.py test_trading_system --full-test')
                self.stdout.write('   2. python manage.py test_trading_system --test-manual-trade')
                
            else:
                self.stdout.write('⚠️  System Status: WORKERS NEEDED')
                self.stdout.write('   Workers: 0 active')
                self.stdout.write('   Recommendation: Start Celery workers')
                
                self.stdout.write('\n🔧 Action Required:')
                self.stdout.write('   1. Open a new terminal')
                if os.name == 'nt':
                    self.stdout.write('   2. Run: celery -A tradevision worker --loglevel=info --pool=solo')
                else:
                    self.stdout.write('   2. Run: celery -A tradevision worker --loglevel=info')
                self.stdout.write('   3. Keep terminal open while testing')
                self.stdout.write('   4. Run tests in original terminal')
                
        except Exception as e:
            self.stdout.write('❌ System Status: CONFIGURATION ERROR')
            self.stdout.write(f'   Error: {e}')
            
            self.stdout.write('\n🔧 Troubleshooting Steps:')
            self.stdout.write('   1. Check tradevision/celery.py exists')
            self.stdout.write('   2. Check CELERY_BROKER_URL in settings')
            self.stdout.write('   3. Start message broker (Redis/RabbitMQ)')
            self.stdout.write('   4. Run: python manage.py check_celery --check-redis')
            
        self.stdout.write('\n📚 Documentation:')
        self.stdout.write('   • Celery docs: https://docs.celeryproject.org/')
        self.stdout.write('   • Django-Celery: https://django-celery.readthedocs.io/')