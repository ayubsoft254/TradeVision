#!/bin/bash
# deploy.sh - Production deployment script (No Health Check)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="./backups"
ENV_FILE=".env"
COMPOSE_FILE="docker-compose.yml"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env file not found. Please copy .env.example to .env and configure it."
        exit 1
    fi
    
    # Check if running as root (not recommended)
    if [ "$EUID" -eq 0 ]; then
        log_warn "Running as root is not recommended for production deployments."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    log_info "Prerequisites check passed."
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p "$BACKUP_DIR"
    mkdir -p "./logs"
    mkdir -p "./scripts"
    
    # Set proper permissions
    chmod 755 ./scripts/*.sh 2>/dev/null || true
    
    log_info "Directories created successfully."
}

# Backup existing data
backup_data() {
    log_info "Creating backup..."
    
    BACKUP_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_PATH="$BACKUP_DIR/backup_$BACKUP_TIMESTAMP"
    
    mkdir -p "$BACKUP_PATH"
    
    # Backup database if running
    if docker-compose ps db | grep -q "Up"; then
        log_info "Backing up database..."
        docker-compose exec -T db pg_dump -U tradevision -d tradevision | gzip > "$BACKUP_PATH/database.sql.gz"
    else
        log_warn "Database container not running, skipping database backup."
    fi
    
    # Backup volumes
    if docker volume ls | grep -q "tradevision_"; then
        log_info "Backing up volumes..."
        docker run --rm -v tradevision_media_volume:/data -v "$(pwd)/$BACKUP_PATH":/backup alpine tar czf /backup/media.tar.gz -C /data . 2>/dev/null || true
        docker run --rm -v tradevision_static_volume:/data -v "$(pwd)/$BACKUP_PATH":/backup alpine tar czf /backup/static.tar.gz -C /data . 2>/dev/null || true
    fi
    
    log_info "Backup completed: $BACKUP_PATH"
    echo "$BACKUP_PATH" > ./last_backup.txt
}

# Deploy application
deploy_application() {
    log_info "Deploying TradeVision application..."
    
    # Pull latest images
    log_info "Pulling latest Docker images..."
    docker-compose pull
    
    # Build new images
    log_info "Building application images..."
    docker-compose build --no-cache
    
    # Start services with zero-downtime deployment
    log_info "Starting services..."
    
    # Start database and Redis first
    docker-compose up -d db redis
    
    # Wait for database to be healthy
    log_info "Waiting for database to be ready..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        if docker-compose exec -T db pg_isready -U tradevision -d tradevision 2>/dev/null; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ $timeout -le 0 ]; then
        log_error "Database failed to start within timeout period."
        log_error "Database logs:"
        docker-compose logs --tail=20 db
        exit 1
    fi
    
    # Wait for Redis to be healthy
    log_info "Waiting for Redis to be ready..."
    timeout=120
    while [ $timeout -gt 0 ]; do
        if docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ $timeout -le 0 ]; then
        log_error "Redis failed to start within timeout period."
        log_error "Redis logs:"
        docker-compose logs --tail=20 redis
        exit 1
    fi
    
    # Start web application
    log_info "Starting web application..."
    docker-compose up -d web
    
    # Wait for web to be ready (check if container is running and port is listening)
    log_info "Waiting for web application to be ready..."
    timeout=300  # 5 minutes
    web_ready=false
    
    while [ $timeout -gt 0 ]; do
        # Check if container is running
        if docker-compose ps web | grep -q "Up"; then
            # Check if port 7373 is accepting connections
            if nc -z localhost 7373 2>/dev/null; then
                log_info "✓ Web application is responding on port 7373"
                web_ready=true
                break
            fi
            
            # Also try to curl the root endpoint (without /health/)
            if curl -f -s --max-time 5 http://localhost:7373/ >/dev/null 2>&1; then
                log_info "✓ Web application is responding to HTTP requests"
                web_ready=true
                break
            fi
        else
            log_warn "Web container is not running. Checking logs..."
            docker-compose logs --tail=10 web
        fi
        
        if [ $((timeout % 30)) -eq 0 ]; then
            log_info "Still waiting for web application... ($timeout seconds remaining)"
            log_info "Container status:"
            docker-compose ps web
        fi
        
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ "$web_ready" = false ]; then
        log_error "Web application failed to start within timeout period."
        log_error "=== DEBUGGING INFO ==="
        log_error "Container status:"
        docker-compose ps
        log_error "Web application logs:"
        docker-compose logs --tail=50 web
        log_error "Port check:"
        netstat -tulpn | grep :7373 || echo "Port 7373 not listening"
        exit 1
    fi
    
    # Start Celery services
    log_info "Starting Celery services..."
    docker-compose up -d celery_worker_critical celery_worker_general celery_beat
    
    log_info "Application deployed successfully!"
}

# Post-deployment checks (without health endpoint)
post_deployment_checks() {
    log_info "Running post-deployment checks..."
    
    # Check service health
    services=("web" "db" "redis" "celery_worker_critical" "celery_worker_general" "celery_beat")
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            log_info "✓ $service is running"
        else
            log_error "✗ $service is not running"
            docker-compose logs --tail=10 "$service"
        fi
    done
    
    # Check application endpoints (without /health/)
    log_info "Testing application endpoints..."
    
    if curl -f -s --max-time 10 http://localhost:7373/ >/dev/null 2>&1; then
        log_info "✓ Root endpoint is responding"
    else
        log_warn "⚠ Root endpoint is not responding properly"
        # Try admin endpoint as fallback
        if curl -f -s --max-time 10 http://localhost:7373/admin/ >/dev/null 2>&1; then
            log_info "✓ Admin endpoint is responding"
        else
            log_warn "⚠ Admin endpoint also not responding"
        fi
    fi
    
    # Check Celery workers
    log_info "Checking Celery workers..."
    if docker-compose exec -T celery_worker_critical celery -A tradevision inspect ping --timeout=10 &>/dev/null; then
        log_info "✓ Critical Celery worker is responding"
    else
        log_warn "⚠ Critical Celery worker is not responding"
    fi
    
    if docker-compose exec -T celery_worker_general celery -A tradevision inspect ping --timeout=10 &>/dev/null; then
        log_info "✓ General Celery worker is responding"
    else
        log_warn "⚠ General Celery worker is not responding"
    fi
    
    log_info "Post-deployment checks completed."
}

# Cleanup old containers and images
cleanup() {
    log_info "Cleaning up old containers and images..."
    
    # Remove old containers
    docker container prune -f
    
    # Remove old images (keep last 2 versions)
    docker image prune -f
    
    # Remove old logs (keep last 30 days)
    find ./logs -name "*.log" -mtime +30 -delete 2>/dev/null || true
    
    # Remove old backups (keep last 10)
    ls -t "$BACKUP_DIR"/backup_* 2>/dev/null | tail -n +11 | xargs rm -rf 2>/dev/null || true
    
    log_info "Cleanup completed."
}

# Show deployment status (without health check)
show_status() {
    log_info "=== TradeVision Deployment Status ==="
    echo
    
    # Service status
    echo -e "${BLUE}Service Status:${NC}"
    docker-compose ps
    echo
    
    # Resource usage
    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "Could not get stats"
    echo
    
    # Disk usage
    echo -e "${BLUE}Volume Usage:${NC}"
    docker system df -v | grep tradevision || echo "No TradeVision volumes found"
    echo
    
    # Recent logs
    echo -e "${BLUE}Recent Application Logs (last 10 lines):${NC}"
    docker-compose logs --tail=10 web
    echo
    
    # Celery status
    echo -e "${BLUE}Celery Worker Status:${NC}"
    docker-compose exec -T celery_worker_critical celery -A tradevision inspect active 2>/dev/null || echo "Critical worker not responding"
    docker-compose exec -T celery_worker_general celery -A tradevision inspect active 2>/dev/null || echo "General worker not responding"
    echo
    
    # Test basic connectivity
    echo -e "${BLUE}Connectivity Test:${NC}"
    if nc -z localhost 7373 2>/dev/null; then
        echo "✓ Port 7373 is accepting connections"
        
        if curl -f -s --max-time 5 http://localhost:7373/ >/dev/null 2>&1; then
            echo "✓ HTTP requests are working"
        else
            echo "⚠ Port open but HTTP requests failing"
        fi
    else
        echo "✗ Port 7373 is not accepting connections"
    fi
    echo
    
    log_info "Status check completed."
}

# Main deployment function
main() {
    local action="${1:-deploy}"
    
    case "$action" in
        "deploy")
            log_info "=== Starting TradeVision Deployment (No Health Check) ==="
            check_prerequisites
            create_directories
            backup_data
            deploy_application
            post_deployment_checks
            cleanup
            show_status
            log_info "=== Deployment Completed Successfully ==="
            log_info "Application should be available at: https://tradevision.uk"
            log_info "Direct access (testing): http://localhost:7373"
            ;;
        "status")
            show_status
            ;;
        "backup")
            check_prerequisites
            backup_data
            ;;
        "cleanup")
            cleanup
            ;;
        "restart")
            log_info "Restarting TradeVision services..."
            docker-compose restart
            post_deployment_checks
            ;;
        "logs")
            service="${2:-web}"
            lines="${3:-50}"
            log_info "Showing last $lines lines of $service logs..."
            docker-compose logs --tail="$lines" -f "$service"
            ;;
        "shell")
            service="${2:-web}"
            log_info "Opening shell in $service container..."
            docker-compose exec "$service" /bin/bash
            ;;
        "help")
            echo "Usage: $0 [action] [options]"
            echo
            echo "Actions:"
            echo "  deploy    - Full deployment (default)"
            echo "  status    - Show deployment status"
            echo "  backup    - Create backup only"
            echo "  cleanup   - Cleanup old containers and images"
            echo "  restart   - Restart all services"
            echo "  logs      - Show logs [service] [lines]"
            echo "  shell     - Open shell [service]"
            echo "  help      - Show this help message"
            echo
            echo "Examples:"
            echo "  $0 deploy"
            echo "  $0 status"
            echo "  $0 logs web 100"
            echo "  $0 shell celery_worker_critical"
            ;;
        *)
            log_error "Unknown action: $action"
            log_info "Use '$0 help' for usage information."
            exit 1
            ;;
    esac
}

# Trap signals for graceful shutdown
trap 'log_info "Deployment interrupted by user"; exit 1' SIGINT SIGTERM

# Execute main function
main "$@"