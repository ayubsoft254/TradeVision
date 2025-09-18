#!/bin/bash
# Simple entrypoint.sh - No health checks

set -e

SERVICE_TYPE="${1:-web}"

# Common environment setup
export PYTHONPATH=/app:$PYTHONPATH
export C_FORCE_ROOT=1

# Logging
LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"

log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Simple wait function
wait_for_services() {
    log_info "Waiting for dependencies..."
    
    # Wait for database
    log_info "Waiting for database..."
    /app/scripts/wait-for-it.sh db 5432 120
    
    # Wait for Redis
    log_info "Waiting for Redis..."
    /app/scripts/wait-for-it.sh redis 6379 60
}

# Simple database setup
setup_database() {
    log_info "Setting up database..."
    
    python manage.py migrate --noinput
    python manage.py migrate django_celery_beat --noinput || true
    python manage.py createcachetable || true
    python manage.py collectstatic --noinput --clear
    
    # Create superuser
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@tradevision.com', 'admin123')
    print('Superuser created: admin/admin123')
" || true
}

# Service functions
start_web() {
    log_info "Starting Django web server..."
    
    wait_for_services
    setup_database
    
    log_info "Starting Gunicorn on port 8000..."
    exec gunicorn tradevision.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --timeout 60 \
        --access-logfile "$LOG_DIR/gunicorn-access.log" \
        --error-logfile "$LOG_DIR/gunicorn-error.log" \
        --log-level info
}

start_celery_worker_critical() {
    log_info "Starting critical Celery worker..."
    
    wait_for_services
    sleep 60  # Wait for web to be ready
    
    exec celery -A tradevision worker \
        --loglevel=info \
        --concurrency=1 \
        --hostname=critical@%h \
        --logfile="$LOG_DIR/celery-critical.log" \
        -Q critical,trading
}

start_celery_worker_general() {
    log_info "Starting general Celery worker..."
    
    wait_for_services
    sleep 90  # Wait longer for web to be ready
    
    exec celery -A tradevision worker \
        --loglevel=info \
        --concurrency=3 \
        --hostname=general@%h \
        --logfile="$LOG_DIR/celery-general.log" \
        -Q payments,security,maintenance,notifications,default
}

start_celery_beat() {
    log_info "Starting Celery beat..."
    
    wait_for_services
    sleep 60
    
    exec celery -A tradevision beat \
        --loglevel=info \
        --scheduler=django_celery_beat.schedulers:DatabaseScheduler \
        --logfile="$LOG_DIR/celery-beat.log"
}

start_flower() {
    log_info "Starting Flower..."
    
    wait_for_services
    sleep 90
    
    exec celery -A tradevision flower \
        --port=5555 \
        --broker="${CELERY_BROKER_URL}" \
        --basic_auth="${FLOWER_BASIC_AUTH:-admin:flower123}"
}

# Main logic
log_info "=== TradeVision $SERVICE_TYPE Starting ==="

case "$SERVICE_TYPE" in
    "web")
        start_web
        ;;
    "celery-worker-critical")
        start_celery_worker_critical
        ;;
    "celery-worker-general")
        start_celery_worker_general
        ;;
    "celery-beat")
        start_celery_beat
        ;;
    "flower")
        start_flower
        ;;
    *)
        log_error "Unknown service: $SERVICE_TYPE"
        exit 1
        ;;
esac