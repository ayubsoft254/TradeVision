#!/bin/bash
# healthcheck.sh - Health check script for containers

set -e

# Determine service type from environment or command line
SERVICE_TYPE="${1:-${CONTAINER_SERVICE:-web}}"

# Health check functions
check_web() {
    # Check if Django is responding
    if curl -f -s http://localhost:8000/health/ > /dev/null 2>&1; then
        echo "Web service: OK"
        return 0
    else
        echo "Web service: FAILED - HTTP health check failed"
        return 1
    fi
}

check_celery_worker() {
    # Check if Celery worker is responding
    if celery -A tradevision inspect ping -d celery@$(hostname) --timeout=10 > /dev/null 2>&1; then
        echo "Celery worker: OK"
        return 0
    else
        echo "Celery worker: FAILED - Worker not responding"
        return 1
    fi
}

check_celery_beat() {
    # Check if Celery beat process is running
    if pgrep -f 'celery.*beat' > /dev/null 2>&1; then
        echo "Celery beat: OK"
        return 0
    else
        echo "Celery beat: FAILED - Beat process not found"
        return 1
    fi
}

check_flower() {
    # Check if Flower is responding
    if curl -f -s http://localhost:5555/ > /dev/null 2>&1; then
        echo "Flower: OK"
        return 0
    else
        echo "Flower: FAILED - HTTP health check failed"
        return 1
    fi
}

# Main health check logic
main() {
    case "$SERVICE_TYPE" in
        "web")
            check_web
            ;;
        "celery-worker")
            check_celery_worker
            ;;
        "celery-beat")
            check_celery_beat
            ;;
        "flower")
            check_flower
            ;;
        *)
            echo "Unknown service type: $SERVICE_TYPE"
            exit 1
            ;;
    esac
}

main "$@"