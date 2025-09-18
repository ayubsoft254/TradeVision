#!/bin/bash
# monitor.sh - Monitoring and alerting script for TradeVision

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ALERT_EMAIL="${ALERT_EMAIL:-admin@tradevision.uk}"
LOG_FILE="/tmp/tradevision_monitor.log"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Send alert function
send_alert() {
    local level="$1"
    local message="$2"
    local service="$3"
    
    log_error "ALERT [$level]: $message"
    
    # Send email alert if configured
    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "TradeVision Alert [$level]: $service" "$ALERT_EMAIL"
    fi
    
    # Send Slack alert if configured
    if [ -n "$SLACK_WEBHOOK" ] && command -v curl &> /dev/null; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 TradeVision Alert [$level]: $message\"}" \
            "$SLACK_WEBHOOK" &>/dev/null || true
    fi
}

# Check service health
check_service_health() {
    local service="$1"
    local expected_status="Up"
    
    if docker-compose ps "$service" 2>/dev/null | grep -q "$expected_status"; then
        return 0
    else
        return 1
    fi
}

# Check web application
check_web_health() {
    local url="http://localhost:7373/health/"
    local timeout=10
    
    if curl -f -s --max-time "$timeout" "$url" | grep -q -E "ok|healthy"; then
        return 0
    else
        return 1
    fi
}

# Check celery workers
check_celery_health() {
    local worker_type="$1"
    
    if docker-compose exec -T "celery_worker_$worker_type" celery -A tradevision inspect ping --timeout=10 &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Check database connectivity
check_database_health() {
    if docker-compose exec -T db pg_isready -U tradevision -d tradevision &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Check Redis connectivity
check_redis_health() {
    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        return 0
    else
        return 1
    fi
}

# Check disk space
check_disk_space() {
    local threshold=85
    local usage
    
    usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -gt "$threshold" ]; then
        send_alert "CRITICAL" "Disk usage is ${usage}% (threshold: ${threshold}%)" "System"
        return 1
    elif [ "$usage" -gt 75 ]; then
        log_warn "Disk usage is ${usage}%"
    fi
    
    return 0
}

# Check memory usage
check_memory_usage() {
    local threshold=90
    local usage
    
    usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [ "$usage" -gt "$threshold" ]; then
        send_alert "CRITICAL" "Memory usage is ${usage}% (threshold: ${threshold}%)" "System"
        return 1
    elif [ "$usage" -gt 75 ]; then
        log_warn "Memory usage is ${usage}%"
    fi
    
    return 0
}

# Check SSL certificate expiry
check_ssl_certificate() {
    local domain="tradevision.uk"
    local days_threshold=30
    
    if command -v openssl &> /dev/null; then
        local expiry_date
        local days_until_expiry
        
        expiry_date=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
        days_until_expiry=$(( ($(date -d "$expiry_date" +%s) - $(date +%s)) / 86400 ))
        
        if [ "$days_until_expiry" -lt "$days_threshold" ]; then
            send_alert "WARNING" "SSL certificate for $domain expires in $days_until_expiry days" "SSL"
            return 1
        fi
    fi
    
    return 0
}

# Check trading tasks
check_trading_tasks() {
    local critical_queues=("critical" "trading")
    
    for queue in "${critical_queues[@]}"; do
        # Check if there are stuck tasks (older than 1 hour)
        local stuck_count
        stuck_count=$(docker-compose exec -T celery_worker_critical celery -A tradevision inspect active 2>/dev/null | grep -c "$(date -d '1 hour ago' '+%Y-%m-%d')" || echo "0")
        
        if [ "$stuck_count" -gt 0 ]; then
            send_alert "WARNING" "Found $stuck_count stuck tasks in $queue queue" "Celery"
        fi
    done
}

# Generate system report
generate_system_report() {
    local report_file="/tmp/tradevision_system_report_$(date +%Y%m%d_%H%M%S).txt"
    
    {
        echo "=== TradeVision System Report ==="
        echo "Generated: $(date)"
        echo
        
        echo "=== Service Status ==="
        docker-compose ps
        echo
        
        echo "=== Resource Usage ==="
        docker stats --no-stream
        echo
        
        echo "=== Disk Usage ==="
        df -h
        echo
        
        echo "=== Memory Usage ==="
        free -h
        echo
        
        echo "=== Recent Logs (Web) ==="
        docker-compose logs --tail=20 web
        echo
        
        echo "=== Recent Logs (Celery Critical) ==="
        docker-compose logs --tail=20 celery_worker_critical
        echo
        
        echo "=== Celery Active Tasks ==="
        docker-compose exec -T celery_worker_critical celery -A tradevision inspect active 2>/dev/null || echo "No active tasks"
        echo
        
    } > "$report_file"
    
    echo "$report_file"
}

# Main monitoring function
monitor_system() {
    local failed_checks=0
    
    log_info "Starting TradeVision system monitoring..."
    
    # Check core services
    services=("db" "redis" "web" "celery_worker_critical" "celery_worker_general" "celery_beat")
    
    for service in "${services[@]}"; do
        if check_service_health "$service"; then
            log_info "✓ $service is healthy"
        else
            log_error "✗ $service is unhealthy"
            send_alert "CRITICAL" "$service container is not running properly" "$service"
            ((failed_checks++))
        fi
    done
    
    # Check web application endpoint
    if check_web_health; then
        log_info "✓ Web application is responding"
    else
        log_error "✗ Web application is not responding"
        send_alert "CRITICAL" "Web application health check failed" "Web"
        ((failed_checks++))
    fi
    
    # Check database connectivity
    if check_database_health; then
        log_info "✓ Database is accessible"
    else
        log_error "✗ Database is not accessible"
        send_alert "CRITICAL" "Database connectivity failed" "Database"
        ((failed_checks++))
    fi
    
    # Check Redis connectivity
    if check_redis_health; then
        log_info "✓ Redis is accessible"
    else
        log_error "✗ Redis is not accessible"
        send_alert "CRITICAL" "Redis connectivity failed" "Redis"
        ((failed_checks++))
    fi
    
    # Check Celery workers
    for worker in "critical" "general"; do
        if check_celery_health "$worker"; then
            log_info "✓ Celery $worker worker is responding"
        else
            log_warn "⚠ Celery $worker worker is not responding"
            send_alert "WARNING" "Celery $worker worker is not responding" "Celery"
            ((failed_checks++))
        fi
    done
    
    # Check system resources
    check_disk_space || ((failed_checks++))
    check_memory_usage || ((failed_checks++))
    
    # Check SSL certificate
    check_ssl_certificate || ((failed_checks++))
    
    # Check trading tasks
    check_trading_tasks
    
    if [ "$failed_checks" -eq 0 ]; then
        log_info "✓ All system checks passed"
        return 0
    else
        log_error "✗ $failed_checks system checks failed"
        return 1
    fi
}

# Performance metrics collection
collect_metrics() {
    local metrics_file="/tmp/tradevision_metrics_$(date +%Y%m%d_%H%M%S).json"
    
    {
        echo "{"
        echo "  \"timestamp\": \"$(date -Iseconds)\","
        echo "  \"services\": {"
        
        # Service status
        services=("db" "redis" "web" "celery_worker_critical" "celery_worker_general" "celery_beat")
        for i in "${!services[@]}"; do
            service="${services[$i]}"
            if check_service_health "$service"; then
                status="healthy"
            else
                status="unhealthy"
            fi
            echo "    \"$service\": \"$status\""
            [ $i -lt $((${#services[@]} - 1)) ] && echo ","
        done
        
        echo "  },"
        echo "  \"system\": {"
        echo "    \"disk_usage\": \"$(df / | awk 'NR==2 {print $5}')\","
        echo "    \"memory_usage\": \"$(free | awk 'NR==2{printf "%.0f%%", $3*100/$2}')\","
        echo "    \"load_average\": \"$(uptime | awk -F'load average:' '{print $2}' | xargs)\""
        echo "  },"
        echo "  \"docker\": {"
        echo "    \"containers_running\": $(docker ps -q | wc -l),"
        echo "    \"images_count\": $(docker images -q | wc -l)"
        echo "  }"
        echo "}"
    } > "$metrics_file"
    
    echo "$metrics_file"
}

# Auto-healing function
auto_heal() {
    local service="$1"
    
    log_info "Attempting to auto-heal $service..."
    
    case "$service" in
        "web"|"celery_worker_critical"|"celery_worker_general"|"celery_beat")
            docker-compose restart "$service"
            sleep 30
            if check_service_health "$service"; then
                log_info "✓ $service auto-healing successful"
                return 0
            else
                log_error "✗ $service auto-healing failed"
                return 1
            fi
            ;;
        *)
            log_warn "Auto-healing not implemented for $service"
            return 1
            ;;
    esac
}

# Main function
main() {
    local action="${1:-monitor}"
    
    case "$action" in
        "monitor")
            monitor_system
            ;;
        "report")
            report_file=$(generate_system_report)
            log_info "System report generated: $report_file"
            cat "$report_file"
            ;;
        "metrics")
            metrics_file=$(collect_metrics)
            log_info "Metrics collected: $metrics_file"
            cat "$metrics_file"
            ;;
        "heal")
            service="${2:-}"
            if [ -n "$service" ]; then
                auto_heal "$service"
            else
                log_error "Service name required for healing"
                exit 1
            fi
            ;;
        "continuous")
            interval="${2:-300}"  # 5 minutes default
            log_info "Starting continuous monitoring (interval: ${interval}s)..."
            while true; do
                monitor_system
                sleep "$interval"
            done
            ;;
        "help")
            echo "Usage: $0 [action] [options]"
            echo
            echo "Actions:"
            echo "  monitor     - Run monitoring checks (default)"
            echo "  report      - Generate detailed system report"
            echo "  metrics     - Collect system metrics in JSON format"
            echo "  heal        - Attempt auto-healing [service]"
            echo "  continuous  - Run continuous monitoring [interval_seconds]"
            echo "  help        - Show this help message"
            echo
            echo "Examples:"
            echo "  $0 monitor"
            echo "  $0 report"
            echo "  $0 heal web"
            echo "  $0 continuous 300"
            ;;
        *)
            log_error "Unknown action: $action"
            echo "Use '$0 help' for usage information."
            exit 1
            ;;
    esac
}

main "$@"