#!/bin/bash
# Simple deploy.sh - No health checks, just deploy

set -e

# Colors for output
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

# Simple deployment
deploy() {
    log_info "=== Simple TradeVision Deployment ==="
    
    # Clean up
    log_info "Cleaning up existing containers..."
    docker-compose down -v
    
    # Build fresh
    log_info "Building images..."
    docker-compose build --no-cache
    
    # Start database and Redis first
    log_info "Starting database and Redis..."
    docker-compose up -d db redis
    
    # Wait a bit for them to initialize
    log_info "Waiting for services to initialize..."
    sleep 30
    
    # Start web service
    log_info "Starting web application..."
    docker-compose up -d web
    
    # Wait for web to start
    log_info "Waiting for web service to start..."
    sleep 60
    
    # Start Celery services
    log_info "Starting Celery services..."
    docker-compose up -d celery_worker_critical celery_worker_general celery_beat
    
    log_info "=== Deployment Complete ==="
    log_info "Application should be available at: http://localhost:7373"
    
    # Show status
    echo
    log_info "Service Status:"
    docker-compose ps
    
    echo
    log_info "Recent logs:"
    docker-compose logs --tail=10 web
}

# Quick status check
status() {
    log_info "=== Service Status ==="
    docker-compose ps
    
    echo
    log_info "Port Check:"
    if nc -z localhost 7373 2>/dev/null; then
        echo "✓ Port 7373 is accessible"
        if curl -s http://localhost:7373/ >/dev/null 2>&1; then
            echo "✓ Web application is responding"
        else
            echo "⚠ Port open but web app may not be ready"
        fi
    else
        echo "✗ Port 7373 is not accessible"
    fi
}

# Show logs
logs() {
    service="${1:-web}"
    lines="${2:-50}"
    log_info "Showing logs for $service (last $lines lines):"
    docker-compose logs --tail="$lines" -f "$service"
}

# Restart services
restart() {
    log_info "Restarting all services..."
    docker-compose restart
    sleep 30
    status
}

# Stop all services
stop() {
    log_info "Stopping all services..."
    docker-compose down
}

# Start services (if already built)
start() {
    log_info "Starting services..."
    docker-compose up -d
    sleep 30
    status
}

# Open shell in container
shell() {
    service="${1:-web}"
    log_info "Opening shell in $service container..."
    docker-compose exec "$service" /bin/bash
}

# Main function
main() {
    case "${1:-deploy}" in
        "deploy")
            deploy
            ;;
        "status")
            status
            ;;
        "logs")
            logs "$2" "$3"
            ;;
        "restart")
            restart
            ;;
        "stop")
            stop
            ;;
        "start")
            start
            ;;
        "shell")
            shell "$2"
            ;;
        "help")
            echo "Usage: $0 [action] [options]"
            echo
            echo "Actions:"
            echo "  deploy    - Full deployment (default)"
            echo "  status    - Show service status"
            echo "  logs      - Show logs [service] [lines]"
            echo "  restart   - Restart all services"
            echo "  start     - Start services"
            echo "  stop      - Stop all services"
            echo "  shell     - Open shell [service]"
            echo "  help      - Show this help"
            echo
            echo "Examples:"
            echo "  $0 deploy"
            echo "  $0 status"
            echo "  $0 logs web 100"
            echo "  $0 shell celery_worker_critical"
            ;;
        *)
            log_error "Unknown action: $1"
            log_info "Use '$0 help' for usage information."
            exit 1
            ;;
    esac
}

# Run main function
main "$@"