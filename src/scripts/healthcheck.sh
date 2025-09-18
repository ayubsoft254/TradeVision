#!/bin/bash
# healthcheck.sh - Health check script for different services

set -e

SERVICE_TYPE="${1:-web}"

case "$SERVICE_TYPE" in
    "web")
        # Check if Django is responding on internal port 8000
        curl -f http://localhost:8000/health/ > /dev/null 2>&1 || \
        curl -f http://localhost:8000/ > /dev/null 2>&1 || \
        curl -f http://127.0.0.1:8000/ > /dev/null 2>&1 || \
        # If no health endpoint, check if port is listening
        nc -z localhost 8000
        ;;
    "celery-worker"|"celery-worker-critical"|"celery-worker-general")
        # Check if celery worker is responding
        celery -A tradevision inspect ping -d celery@$(hostname) --timeout=10 > /dev/null 2>&1
        ;;
    "celery-beat")
        # Check if celery beat process is running
        pgrep -f 'celery.*beat' > /dev/null 2>&1
        ;;
    "flower")
        # Check if flower is responding
        curl -f http://localhost:5555/ > /dev/null 2>&1
        ;;
    *)
        echo "Unknown service type: $SERVICE_TYPE" >&2
        exit 1
        ;;
esac

exit 0