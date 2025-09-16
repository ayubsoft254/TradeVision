# celery.py (in project root)
import os
from celery import Celery
from django.conf import settings
from django.utils import timezone
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')

app = Celery('tradevision')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule - Complete Trading & Payment Automation
app.conf.beat_schedule = {
    
    # =============================================================================
    # TRADING TASKS (Core Business Logic)
    # =============================================================================
    
    'process-completed-trades': {
        'task': 'apps.trading.tasks.process_completed_trades',
        'schedule': 60.0,  # Every minute - CRITICAL for daily profits
        'options': {
            'expires': 45,  # Task expires in 45 seconds
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 30,
                'interval_step': 30,
                'interval_max': 120,
            }
        }
    },
    
    'auto-initiate-daily-trades': {
        'task': 'apps.trading.tasks.auto_initiate_daily_trades',
        'schedule': 3600.0,  # Every hour during trading hours
        'options': {
            'expires': 1800,  # 30 minutes to complete
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 300,
                'interval_step': 300,
                'interval_max': 900,
            }
        }
    },
    
    'check-investment-maturity': {
        'task': 'apps.trading.tasks.check_investment_maturity',
        'schedule': 86400.0,  # Daily at midnight
        'options': {
            'expires': 3600,  # 1 hour to complete
        }
    },
    
    'update-wallet-balances': {
        'task': 'apps.trading.tasks.update_wallet_balances',
        'schedule': 43200.0,  # Twice daily (every 12 hours)
        'options': {
            'expires': 1800,  # 30 minutes to complete
        }
    },
    
    'cleanup-failed-trades': {
        'task': 'apps.trading.tasks.cleanup_failed_trades',
        'schedule': 86400.0,  # Daily maintenance
        'options': {
            'expires': 1800,  # 30 minutes to complete
        }
    },
    
    'update-platform-statistics': {
        'task': 'apps.trading.tasks.update_platform_statistics',
        'schedule': 21600.0,  # Every 6 hours
        'options': {
            'expires': 600,  # 10 minutes to complete
        }
    },
    
    'send-profit-notifications': {
        'task': 'apps.trading.tasks.send_profit_notifications',
        'schedule': 86400.0,  # Daily notifications
        'options': {
            'expires': 3600,  # 1 hour to complete
        }
    },
    
    # =============================================================================
    # PAYMENT TASKS (Financial Operations)
    # =============================================================================
    
    'process-pending-deposits': {
        'task': 'apps.payments.tasks.process_pending_deposits',
        'schedule': 300.0,  # Every 5 minutes
        'options': {
            'expires': 240,  # 4 minutes to complete
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 60,
                'interval_step': 60,
                'interval_max': 180,
            }
        }
    },
    
    'process-withdrawal-requests': {
        'task': 'apps.payments.tasks.process_withdrawal_requests',
        'schedule': 600.0,  # Every 10 minutes
        'options': {
            'expires': 480,  # 8 minutes to complete
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 120,
                'interval_step': 120,
                'interval_max': 360,
            }
        }
    },
    
    'auto-approve-small-deposits': {
        'task': 'apps.payments.tasks.auto_approve_small_deposits',
        'schedule': 900.0,  # Every 15 minutes
        'options': {
            'expires': 600,  # 10 minutes to complete
        }
    },

    'check-binance-payments': {
        'task': 'apps.payments.tasks.check_binance_payments_task',
        'schedule': 300.0,  # 5 minutes
        'options': {'queue': 'payments'}
    },
    
    # Clean up old pending payments daily at 2 AM
    'cleanup-old-payments': {
        'task': 'apps.payments.tasks.cleanup_old_pending_payments',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'maintenance'}
    },
    
    # Generate daily report at 11:59 PM
    'daily-payment-report': {
        'task': 'apps.payments.tasks.generate_payment_report',
        'schedule': crontab(hour=23, minute=59),
        'options': {'queue': 'reports'}
    },
    
    'detect-suspicious-activity': {
        'task': 'apps.payments.tasks.detect_suspicious_activity',
        'schedule': 3600.0,  # Every hour
        'options': {
            'expires': 1800,  # 30 minutes to complete
        }
    },
    
    'check-failed-transactions': {
        'task': 'apps.payments.tasks.check_failed_transactions',
        'schedule': 86400.0,  # Daily cleanup
        'options': {
            'expires': 1800,  # 30 minutes to complete
        }
    },
    
    'update-payment-provider-ratings': {
        'task': 'apps.payments.tasks.update_payment_provider_ratings',
        'schedule': 86400.0,  # Daily rating updates
        'options': {
            'expires': 3600,  # 1 hour to complete
        }
    },
    
    'generate-payment-reports': {
        'task': 'apps.payments.tasks.generate_payment_reports',
        'schedule': 86400.0,  # Daily reports
        'options': {
            'expires': 1800,  # 30 minutes to complete
        }
    },
}

# Celery Configuration Settings
app.conf.update(
    # Timezone Configuration
    timezone='UTC',
    enable_utc=True,
    
    # Task Configuration
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker Configuration
    worker_prefetch_multiplier=1,  # One task at a time for consistency
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    worker_disable_rate_limits=False,
    
    # Beat Configuration
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
    
    # Task Routes - Prioritize critical tasks
    task_routes={
        'apps.trading.tasks.process_completed_trades': {'queue': 'critical'},
        'apps.trading.tasks.auto_initiate_daily_trades': {'queue': 'trading'},
        'apps.payments.tasks.process_pending_deposits': {'queue': 'payments'},
        'apps.payments.tasks.process_withdrawal_requests': {'queue': 'payments'},
        'apps.payments.tasks.detect_suspicious_activity': {'queue': 'security'},
    },
    
    # Default Queue Configuration
    task_default_queue='default',
    task_default_exchange='default',
    task_default_exchange_type='direct',
    task_default_routing_key='default',
    
    # Queue Configuration
    task_queue_ha_policy='all',
    
    # Security Configuration
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Error Handling
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Rate Limiting
    task_annotations={
        'apps.trading.tasks.process_completed_trades': {'rate_limit': '60/m'},  # Max 60 per minute
        'apps.payments.tasks.process_pending_deposits': {'rate_limit': '20/m'},  # Max 20 per minute
        'apps.payments.tasks.detect_suspicious_activity': {'rate_limit': '1/m'},  # Max 1 per minute
    }
)

# Queue Configuration for Different Task Types
app.conf.task_routes = {
    # Critical Trading Tasks (Highest Priority)
    'apps.trading.tasks.process_completed_trades': {
        'queue': 'critical',
        'priority': 10
    },
    
    # Trading Tasks (High Priority)
    'apps.trading.tasks.auto_initiate_daily_trades': {
        'queue': 'trading', 
        'priority': 8
    },
    'apps.trading.tasks.check_investment_maturity': {
        'queue': 'trading',
        'priority': 7
    },
    'apps.trading.tasks.update_wallet_balances': {
        'queue': 'trading',
        'priority': 6
    },
    
    # Payment Tasks (Medium Priority)
    'apps.payments.tasks.process_pending_deposits': {
        'queue': 'payments',
        'priority': 8
    },
    'apps.payments.tasks.process_withdrawal_requests': {
        'queue': 'payments',
        'priority': 8
    },
    'apps.payments.tasks.auto_approve_small_deposits': {
        'queue': 'payments',
        'priority': 6
    },
    
    # Security Tasks (High Priority)
    'apps.payments.tasks.detect_suspicious_activity': {
        'queue': 'security',
        'priority': 9
    },
    
    # Maintenance Tasks (Low Priority)
    'apps.trading.tasks.cleanup_failed_trades': {
        'queue': 'maintenance',
        'priority': 3
    },
    'apps.payments.tasks.check_failed_transactions': {
        'queue': 'maintenance',
        'priority': 3
    },
    'apps.payments.tasks.update_payment_provider_ratings': {
        'queue': 'maintenance',
        'priority': 2
    },
    'apps.payments.tasks.generate_payment_reports': {
        'queue': 'maintenance',
        'priority': 2
    },
    
    # Notification Tasks (Medium Priority)
    'apps.trading.tasks.send_profit_notifications': {
        'queue': 'notifications',
        'priority': 5
    },
    'apps.payments.tasks.send_deposit_confirmation': {
        'queue': 'notifications',
        'priority': 6
    },
    'apps.payments.tasks.send_withdrawal_confirmation': {
        'queue': 'notifications',
        'priority': 6
    },
}

# Logging Configuration
app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
app.conf.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Health Check Task
@app.task(bind=True)
def debug_task(self):
    """Debug task for health checking"""
    print(f'Request: {self.request!r}')
    return {
        'status': 'healthy',
        'worker_id': self.request.id,
        'timestamp': timezone.now().isoformat()
    }

# Custom Error Handler
@app.task(bind=True)
def error_handler(self, uuid, error, request, traceback):
    """Custom error handler for failed tasks"""
    print(f'Task {uuid} failed: {error}')
    # Here you could send alerts to admins
    return {
        'task_id': uuid,
        'error': str(error),
        'request': request,
        'status': 'failed'
    }

# Performance Monitoring
@app.task(bind=True)
def monitor_queue_health(self):
    """Monitor Celery queue health"""
    try:
        # Get queue statistics
        inspect = app.control.inspect()
        
        # Check active tasks
        active_tasks = inspect.active()
        
        # Check scheduled tasks
        scheduled_tasks = inspect.scheduled()
        
        # Check worker stats
        worker_stats = inspect.stats()
        
        return {
            'status': 'healthy',
            'active_tasks': len(active_tasks) if active_tasks else 0,
            'scheduled_tasks': len(scheduled_tasks) if scheduled_tasks else 0,
            'workers': len(worker_stats) if worker_stats else 0,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }

# Add monitoring task to beat schedule
app.conf.beat_schedule['monitor-queue-health'] = {
    'task': 'celery.monitor_queue_health',
    'schedule': 1800.0,  # Every 30 minutes
    'options': {'expires': 300}
}

# Startup Configuration
if __name__ == '__main__':
    app.start()

# Production Optimizations
if not settings.DEBUG:
    # Production-specific settings
    app.conf.update(
        broker_pool_limit=100,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        result_backend_transport_options={
            'master_name': 'mymaster',
            'retry_on_timeout': True,
        },
        worker_max_memory_per_child=200000,  # 200MB per child
    )