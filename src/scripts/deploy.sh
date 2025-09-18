#!/bin/bash
# deploy.sh - Production deployment script

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
    chmod 755 ./scripts/*.sh
    
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
        docker run --rm -v tradevision_media_volume:/data -v "$(pwd)/$BACKUP_PATH":/backup alpine tar czf /backup/media.tar.gz -C /data .
        docker run --rm -v tradevision_static_volume:/data -v "$(pwd)/$BACKUP_PATH":/backup alpine tar czf /backup/static.tar.gz -C /data .
    fi
    
    log_info "Backup completed: $BACKUP_PATH"
    echo "$BACKUP_PATH" > ./last_backup.txt
}

# Update external Nginx configuration
update_nginx() {
    log_info "Checking Nginx configuration..."
    
    NGINX_SITE="/etc/nginx/sites-available/tradevision"
    NGINX_ENABLED="/etc/nginx/sites-enabled/tradevision"
    
    # Check if we have sudo access and Nginx is installed
    if command -v nginx &> /dev/null && sudo -n true 2>/dev/null; then
        log_info "Updating Nginx configuration with optimizations..."
        
        # Backup current config
        sudo cp "$NGINX_SITE" "$NGINX_SITE.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
        
        # Create optimized Nginx config
        sudo tee "$NGINX_SITE" > /dev/null << 'EOF'
# Redirect www to non-www
server {
    server_name www.tradevision.uk;
    return 301 https://tradevision.uk$request_uri;
    listen 443 ssl http2; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/tradevision.uk/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/tradevision.uk/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

# Main server block
server {
    server_name tradevision.uk;
    
    # Basic settings
    client_max_body_size 50M;
    client_body_buffer_size 1M;
    client_header_buffer_size 8k;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    
    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_req_status 429;
        
        proxy_pass http://localhost:7373;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Authentication endpoints with stricter rate limiting
    location ~ ^/(login|register|password_reset)/ {
        limit_req zone=login burst=5 nodelay;
        limit_req_status 429;
        
        proxy_pass http://localhost:7373;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
    }
    
    # Static files caching
    location /static/ {
        proxy_pass http://localhost:7373;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cache static files
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Vary "Accept-Encoding";
        
        # Gzip compression
        gzip on;
        gzip_vary on;
        gzip_types
            text/css
            text/javascript
            text/xml
            text/plain
            application/javascript
            application/xml+rss
            application/json
            image/svg+xml;
    }
    
    # Media files
    location /media/ {
        proxy_pass http://localhost:7373;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Health check endpoint
    location /health/ {
        proxy_pass http://localhost:7373;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        access_log off;
    }
    
    # All other requests
    location / {
        proxy_pass http://localhost:7373;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
    
    listen 443 ssl http2; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/tradevision.uk/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/tradevision.uk/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

# HTTP to HTTPS redirect
server {
    if ($host = tradevision.uk) {
        return 301 https://$host$request_uri;
    }
    
    listen 80;
    server_name tradevision.uk;
    return 404;
}

server {
    if ($host = www.tradevision.uk) {
        return 301 https://$host$request_uri;
    }
    
    listen 80;
    server_name www.tradevision.uk;
    return 404;
}
EOF
        
        # Test Nginx configuration
        if sudo nginx -t; then
            log_info "Nginx configuration is valid. Reloading Nginx..."
            sudo systemctl reload nginx
        else
            log_error "Nginx configuration test failed. Restoring backup..."
            sudo mv "$NGINX_SITE.backup.$(date +%Y%m%d_%H%M%S)" "$NGINX_SITE"
            exit 1
        fi
    else
        log_warn "Cannot update Nginx configuration automatically. Please update manually if needed."
    fi
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
        if docker-compose exec -T db pg_isready -U tradevision -d tradevision; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ $timeout -le 0 ]; then
        log_error "Database failed to start within timeout period."
        exit 1
    fi
    
    # Start web application
    docker-compose up -d web
    
    # Wait for web to be healthy
    log_info "Waiting for web application to be ready..."
    timeout=180
    while [ $timeout -gt 0 ]; do
        if curl -f http://localhost:7373/health/ &>/dev/null; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ $timeout -le 0 ]; then
        log_error "Web application failed to start within timeout period."
        exit 1
    fi
    
    # Start Celery services
    log_info "Starting Celery services..."
    docker-compose up -d celery_worker_critical celery_worker_general celery_beat
    
    log_info "Application deployed successfully!"
}

# Post-deployment checks
post_deployment_checks() {
    log_info "Running post-deployment checks..."
    
    # Check service health
    services=("web" "db" "redis" "celery_worker_critical" "celery_worker_general" "celery_beat")
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            log_info "✓ $service is running"
        else
            log_error "✗ $service is not running"
            docker-compose logs "$service"
        fi
    done
    
    # Check application endpoints
    log_info "Testing application endpoints..."
    
    if curl -f -s http://localhost:7373/health/ | grep -q "ok\|healthy"; then
        log_info "✓ Health check endpoint is responding"
    else
        log_error "✗ Health check endpoint is not responding properly"
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

# Show deployment status
show_status() {
    log_info "=== TradeVision Deployment Status ==="
    echo
    
    # Service status
    echo -e "${BLUE}Service Status:${NC}"
    docker-compose ps
    echo
    
    # Resource usage
    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
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
    
    log_info "Status check completed."
}

# Main deployment function
main() {
    local action="${1:-deploy}"
    
    case "$action" in
        "deploy")
            log_info "=== Starting TradeVision Deployment ==="
            check_prerequisites
            create_directories
            backup_data
            update_nginx
            deploy_application
            post_deployment_checks
            cleanup
            show_status
            log_info "=== Deployment Completed Successfully ==="
            log_info "Application is available at: https://tradevision.uk"
            log_info "Flower monitoring: http://localhost:5555 (use --profile monitoring)"
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