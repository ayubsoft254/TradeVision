#!/bin/bash
# entrypoint.sh - Main entrypoint script for different services

set -e

# Parse service type
SERVICE_TYPE="${1:-web}"

# Common environment setup
export PYTHONPATH=/app:$PYTHONPATH
export C_FORCE_ROOT=1

# Logging setup
LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"

# Color output functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_debug() {
    if [ "$DEBUG" = "1" ]; then
        echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
    fi
}

# Wait for dependencies
wait_for_services() {
    log_info "Waiting for database..."
    /app/scripts/wait-for-it.sh db 5432 60
    
    log_info "Waiting for Redis..."
    /app/scripts/wait-for-it.sh redis 6379 30
}

# Database operations
setup_database() {
    log_info "Setting up database..."
    
    log_info "Running Django migrations..."
    python manage.py migrate --noinput
    
    log_info "Running django-celery-beat migrations..."
    python manage.py migrate django_celery_beat --noinput
    
    log_info "Creating cache table..."
    python manage.py createcachetable || log_warn "Cache table creation failed or already exists"
    
    # Create superuser if it doesn't exist
    log_info "Creating superuser if needed..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@tradevision.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
" || log_warn "Superuser creation failed"
    
    log_info "Collecting static files..."
    python manage.py collectstatic --noinput --clear
}

# Test connections
test_connections() {
    log_info "Testing database connection..."
    python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('Database connection: OK')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"
    
    log_info "Testing Redis connection..."
    python manage.py shell -c "
import redis
import os
try:
    r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))
    r.ping()
    print('Redis connection: OK')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
"
    
    log_info "Testing Celery broker connection..."
    python manage.py shell -c "
from celery import current_app
try:
    inspect = current_app.control.inspect()
    stats = inspect.stats()
    if stats:
        print('Celery broker connection: OK')
    else:
        print('Celery broker connection: No workers found (expected for web service)')
except Exception as e:
    print(f'Celery broker connection failed: {e}')
"
}

# Service-specific startup functions
start_web() {
    log_info "Starting Django web server..."
    
    wait_for_services
    setup_database
    test_connections
    
    log_info "Starting Gunicorn server on port 8000..."
    exec gunicorn tradevision.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --worker-class sync \
        --worker-connections 1000 \
        --timeout 30 \
        --keepalive 2 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload \
        --access-logfile "$LOG_DIR/gunicorn-access.log" \
        --error-logfile "$LOG_DIR/gunicorn-error.log" \
        --log-level info \
        --capture-output
}

start_celery_worker() {
    log_info "Starting Celery worker..."
    
    wait_for_services
    
    # Wait for web service to complete migrations
    log_info "Waiting for web service to complete setup..."
    sleep 30
    
    test_connections
    
    log_info "Starting Celery worker with optimized settings..."
    exec celery -A tradevision worker \
        --loglevel=info \
        --concurrency=2 \
        --max-tasks-per-child=1000 \
        --time-limit=300 \
        --soft-time-limit=240 \
        --logfile="$LOG_DIR/celery-worker.log" \
        --pidfile="$LOG_DIR/celery-worker.pid" \
        -Q critical,trading,payments,security,maintenance,notifications,default
}

start_celery_beat() {
    log_info "Starting Celery beat scheduler..."
    
    wait_for_services
    
    # Wait for web service and worker
    log_info "Waiting for services to be ready..."
    sleep 45
    
    test_connections
    
    log_info "Starting Celery beat with database scheduler..."
    exec celery -A tradevision beat \
        --loglevel=info \
        --scheduler=django_celery_beat.schedulers:DatabaseScheduler \
        --logfile="$LOG_DIR/celery-beat.log" \
        --pidfile="$LOG_DIR/celery-beat.pid"
}

start_flower() {
    log_info "Starting Flower monitoring..."
    
    wait_for_services
    
    # Wait for celery worker
    log_info "Waiting for Celery worker..."
    sleep 60
    
    log_info "Starting Flower on port 5555..."
    exec celery -A tradevision flower \
        --port=5555 \
        --broker="${CELERY_BROKER_URL}" \
        --basic_auth="${FLOWER_BASIC_AUTH:-admin:flower123}" \
        --logfile="$LOG_DIR/flower.log"
}

# Health check for containers
health_check() {
    case "$SERVICE_TYPE" in
        "web")
            curl -f http://localhost:8000/health/ > /dev/null 2>&1
            ;;
        "celery-worker")
            celery -A tradevision inspect ping -d celery@$(hostname) > /dev/null 2>&1
            ;;
        "celery-beat")
            pgrep -f 'celery.*beat' > /dev/null 2>&1
            ;;
        "flower")
            curl -f http://localhost:5555/ > /dev/null 2>&1
            ;;
        *)
            exit 1
            ;;
    esac
}

# Main execution logic
main() {
    log_info "=== TradeVision Container Startup ==="
    log_info "Service Type: $SERVICE_TYPE"
    log_info "Python Path: $PYTHONPATH"
    log_info "Django Settings: $DJANGO_SETTINGS_MODULE"
    log_info "Time Zone: ${TIME_ZONE:-UTC}"
    
    case "$SERVICE_TYPE" in
        "web")
            start_web
            ;;
        "celery-worker")
            start_celery_worker
            ;;
        "celery-beat")
            start_celery_beat
            ;;
        "flower")
            start_flower
            ;;
        "health")
            health_check
            exit $?
            ;;
        *)
            log_error "Unknown service type: $SERVICE_TYPE"
            log_error "Available types: web, celery-worker, celery-beat, flower, health"
            exit 1
            ;;
    esac
}

# Trap signals for graceful shutdown
trap 'log_info "Received shutdown signal, exiting..."; exit 0' SIGTERM SIGINT

# Execute main function
main "$@"