#!/bin/bash
# backup.sh - Comprehensive backup script for TradeVision

set -e

# Configuration
BACKUP_DIR="./backups"
S3_BUCKET="${S3_BUCKET:-}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_PATH"
    log_info "Created backup directory: $BACKUP_PATH"
}

# Backup database
backup_database() {
    log_info "Starting database backup..."
    
    if ! docker-compose ps db | grep -q "Up"; then
        log_error "Database container is not running"
        return 1
    fi
    
    # Create compressed database backup
    docker-compose exec -T db pg_dump \
        -U tradevision \
        -d tradevision \
        --verbose \
        --clean \
        --no-owner \
        --no-privileges | gzip > "$BACKUP_PATH/database.sql.gz"
    
    # Create backup metadata
    {
        echo "Database Backup Information"
        echo "=========================="
        echo "Timestamp: $(date -Iseconds)"
        echo "Database: tradevision"
        echo "User: tradevision"
        echo "Backup Size: $(du -h "$BACKUP_PATH/database.sql.gz" | cut -f1)"
        echo "Docker Container: $(docker-compose ps -q db)"
        echo "PostgreSQL Version: $(docker-compose exec -T db psql -U tradevision -d tradevision -c 'SELECT version();' | head -n 3 | tail -n 1)"
    } > "$BACKUP_PATH/database_info.txt"
    
    log_info "Database backup completed"
}

# Backup Redis data
backup_redis() {
    log_info "Starting Redis backup..."
    
    if ! docker-compose ps redis | grep -q "Up"; then
        log_error "Redis container is not running"
        return 1
    fi
    
    # Create Redis backup
    docker-compose exec -T redis redis-cli BGSAVE
    
    # Wait for background save to complete
    while [ "$(docker-compose exec -T redis redis-cli LASTSAVE)" = "$(docker-compose exec -T redis redis-cli LASTSAVE)" ]; do
        sleep 1
    done
    
    # Copy Redis dump
    docker cp "$(docker-compose ps -q redis):/data/dump.rdb" "$BACKUP_PATH/redis_dump.rdb" || log_warn "Redis backup may have failed"
    
    log_info "Redis backup completed"
}

# Backup application volumes
backup_volumes() {
    log_info "Starting volume backups..."
    
    # Backup media files
    if docker volume ls | grep -q "tradevision_media_volume"; then
        log_info "Backing up media files..."
        docker run --rm \
            -v tradevision_media_volume:/data \
            -v "$(pwd)/$BACKUP_PATH":/backup \
            alpine tar czf /backup/media_files.tar.gz -C /data .
        log_info "Media files backup completed"
    fi
    
    # Backup static files
    if docker volume ls | grep -q "tradevision_static_volume"; then
        log_info "Backing up static files..."
        docker run --rm \
            -v tradevision_static_volume:/data \
            -v "$(pwd)/$BACKUP_PATH":/backup \
            alpine tar czf /backup/static_files.tar.gz -C /data .
        log_info "Static files backup completed"
    fi
    
    # Backup logs
    if docker volume ls | grep -q "tradevision_logs_volume"; then
        log_info "Backing up log files..."
        docker run --rm \
            -v tradevision_logs_volume:/data \
            -v "$(pwd)/$BACKUP_PATH":/backup \
            alpine tar czf /backup/log_files.tar.gz -C /data .
        log_info "Log files backup completed"
    fi
}

# Backup configuration files
backup_config() {
    log_info "Backing up configuration files..."
    
    # Create config backup directory
    mkdir -p "$BACKUP_PATH/config"
    
    # Backup essential configuration files
    cp docker-compose.yml "$BACKUP_PATH/config/" 2>/dev/null || log_warn "docker-compose.yml not found"
    cp Dockerfile "$BACKUP_PATH/config/" 2>/dev/null || log_warn "Dockerfile not found"
    cp .env "$BACKUP_PATH/config/env.backup" 2>/dev/null || log_warn ".env not found"
    cp -r scripts "$BACKUP_PATH/config/" 2>/dev/null || log_warn "scripts directory not found"
    
    # Backup Nginx configuration
    if [ -f "/etc/nginx/sites-available/tradevision" ]; then
        sudo cp "/etc/nginx/sites-available/tradevision" "$BACKUP_PATH/config/nginx_tradevision.conf" || log_warn "Could not backup Nginx config"
    fi
    
    log_info "Configuration files backup completed"
}

# Create backup manifest
create_manifest() {
    log_info "Creating backup manifest..."
    
    {
        echo "TradeVision Backup Manifest"
        echo "=========================="
        echo "Backup ID: $TIMESTAMP"
        echo "Created: $(date -Iseconds)"
        echo "Server: $(hostname)"
        echo "Backup Path: $BACKUP_PATH"
        echo ""
        echo "Contents:"
        echo "--------"
        find "$BACKUP_PATH" -type f -exec basename {} \; | sort
        echo ""
        echo "File Sizes:"
        echo "----------"
        du -sh "$BACKUP_PATH"/*
        echo ""
        echo "Total Backup Size: $(du -sh "$BACKUP_PATH" | cut -f1)"
        echo ""
        echo "Docker Info:"
        echo "-----------"
        docker-compose ps
        echo ""
        echo "System Info:"
        echo "-----------"
        echo "OS: $(uname -a)"
        echo "Disk Space: $(df -h / | awk 'NR==2 {print $4}') available"
        echo "Memory: $(free -h | awk 'NR==2{print $4}') available"
    } > "$BACKUP_PATH/MANIFEST.txt"
    
    log_info "Backup manifest created"
}

# Compress backup
compress_backup() {
    log_info "Compressing backup..."
    
    cd "$BACKUP_DIR"
    tar czf "backup_${TIMESTAMP}.tar.gz" "backup_${TIMESTAMP}/"
    
    if [ $? -eq 0 ]; then
        rm -rf "backup_${TIMESTAMP}/"
        COMPRESSED_BACKUP="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"
        log_info "Backup compressed: $COMPRESSED_BACKUP"
        log_info "Compressed size: $(du -sh "$COMPRESSED_BACKUP" | cut -f1)"
    else
        log_error "Backup compression failed"
        return 1
    fi
    
    cd - > /dev/null
}

# Upload to cloud storage (if configured)
upload_to_cloud() {
    if [ -n "$S3_BUCKET" ] && command -v aws &> /dev/null; then
        log_info "Uploading backup to S3..."
        
        aws s3 cp "$COMPRESSED_BACKUP" "s3://$S3_BUCKET/tradevision-backups/" \
            --storage-class STANDARD_IA \
            --server-side-encryption AES256
        
        if [ $? -eq 0 ]; then
            log_info "Backup uploaded to S3 successfully"
        else
            log_error "S3 upload failed"
            return 1
        fi
    else
        log_info "S3 upload skipped (not configured or AWS CLI not available)"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping $RETENTION_DAYS days)..."
    
    # Local cleanup
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    # S3 cleanup (if configured)
    if [ -n "$S3_BUCKET" ] && command -v aws &> /dev/null; then
        log_info "Cleaning up old S3 backups..."
        aws s3 ls "s3://$S3_BUCKET/tradevision-backups/" | \
            awk '{print $4}' | \
            grep "backup_.*\.tar\.gz" | \
            while read -r file; do
                # Extract date from filename and compare
                file_date=$(echo "$file" | grep -o '[0-9]\{8\}' | head -1)
                if [ -n "$file_date" ]; then
                    file_timestamp=$(date -d "$file_date" +%s)
                    cutoff_timestamp=$(date -d "$RETENTION_DAYS days ago" +%s)
                    
                    if [ "$file_timestamp" -lt "$cutoff_timestamp" ]; then
                        aws s3 rm "s3://$S3_BUCKET/tradevision-backups/$file"
                        log_info "Deleted old S3 backup: $file"
                    fi
                fi
            done
    fi
    
    log_info "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    if [ -f "$COMPRESSED_BACKUP" ]; then
        # Test if tar archive is valid
        if tar -tzf "$COMPRESSED_BACKUP" > /dev/null 2>&1; then
            log_info "✓ Backup archive is valid"
            
            # Check if database backup is readable
            if tar -tzf "$COMPRESSED_BACKUP" | grep -q "database.sql.gz"; then
                log_info "✓ Database backup included"
            else
                log_warn "⚠ Database backup not found in archive"
            fi
            
            return 0
        else
            log_error "✗ Backup archive is corrupted"
            return 1
        fi
    else
        log_error "✗ Backup file not found"
        return 1
    fi
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    
    # Email notification
    if command -v mail &> /dev/null && [ -n "${ALERT_EMAIL:-}" ]; then
        echo "$message" | mail -s "TradeVision Backup $status" "$ALERT_EMAIL"
    fi
    
    # Slack notification
    if [ -n "${SLACK_WEBHOOK:-}" ] && command -v curl &> /dev/null; then
        local emoji
        case "$status" in
            "SUCCESS") emoji="✅" ;;
            "FAILED") emoji="❌" ;;
            *) emoji="ℹ️" ;;
        esac
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$emoji TradeVision Backup $status: $message\"}" \
            "$SLACK_WEBHOOK" &>/dev/null || true
    fi
}

# Restore function
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Backup file path required"
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_warn "WARNING: This will restore data and may overwrite current data!"
    read -p "Are you sure you want to continue? (yes/no): " -r
    
    if [ "$REPLY" != "yes" ]; then
        log_info "Restore cancelled"
        return 0
    fi
    
    log_info "Starting restore from: $backup_file"
    
    # Extract backup
    local restore_dir="/tmp/tradevision_restore_$(date +%s)"
    mkdir -p "$restore_dir"
    tar -xzf "$backup_file" -C "$restore_dir" --strip-components=1
    
    # Restore database
    if [ -f "$restore_dir/database.sql.gz" ]; then
        log_info "Restoring database..."
        gunzip -c "$restore_dir/database.sql.gz" | \
            docker-compose exec -T db psql -U tradevision -d tradevision
    fi
    
    # Restore volumes
    for volume_backup in "$restore_dir"/*_files.tar.gz; do
        if [ -f "$volume_backup" ]; then
            volume_name=$(basename "$volume_backup" | sed 's/_files\.tar\.gz$//')
            log_info "Restoring $volume_name volume..."
            
            docker run --rm \
                -v "tradevision_${volume_name}_volume:/data" \
                -v "$restore_dir":/backup \
                alpine sh -c "cd /data && tar -xzf /backup/$(basename "$volume_backup")"
        fi
    done
    
    # Cleanup
    rm -rf "$restore_dir"
    
    log_info "Restore completed. Please restart services."
}

# List available backups
list_backups() {
    log_info "Available local backups:"
    
    if ls "$BACKUP_DIR"/backup_*.tar.gz 1> /dev/null 2>&1; then
        for backup in "$BACKUP_DIR"/backup_*.tar.gz; do
            size=$(du -sh "$backup" | cut -f1)
            date_created=$(stat -c %y "$backup" 2>/dev/null || stat -f %Sm "$backup" 2>/dev/null)
            echo "  $(basename "$backup") - $size - $date_created"
        done
    else
        echo "  No local backups found"
    fi
    
    if [ -n "$S3_BUCKET" ] && command -v aws &> /dev/null; then
        log_info "Available S3 backups:"
        aws s3 ls "s3://$S3_BUCKET/tradevision-backups/" --human-readable | \
            grep "backup_.*\.tar\.gz" || echo "  No S3 backups found"
    fi
}

# Main function
main() {
    local action="${1:-backup}"
    
    case "$action" in
        "backup"|"full")
            log_info "=== Starting Full Backup ==="
            
            create_backup_dir
            
            # Run backup components
            backup_database || log_error "Database backup failed"
            backup_redis || log_error "Redis backup failed"
            backup_volumes || log_error "Volume backup failed"
            backup_config || log_error "Config backup failed"
            
            create_manifest
            compress_backup
            
            if verify_backup; then
                upload_to_cloud
                cleanup_old_backups
                send_notification "SUCCESS" "Backup completed successfully: $(basename "$COMPRESSED_BACKUP")"
                log_info "=== Backup Completed Successfully ==="
                log_info "Backup location: $COMPRESSED_BACKUP"
                log_info "Backup size: $(du -sh "$COMPRESSED_BACKUP" | cut -f1)"
            else
                send_notification "FAILED" "Backup verification failed"
                log_error "=== Backup Failed ==="
                exit 1
            fi
            ;;
        "database")
            log_info "=== Database Only Backup ==="
            create_backup_dir
            backup_database
            create_manifest
            compress_backup
            verify_backup
            ;;
        "config")
            log_info "=== Configuration Only Backup ==="
            create_backup_dir
            backup_config
            create_manifest
            compress_backup
            ;;
        "restore")
            backup_file="${2:-}"
            restore_backup "$backup_file"
            ;;
        "list")
            list_backups
            ;;
        "cleanup")
            cleanup_old_backups
            ;;
        "verify")
            backup_file="${2:-$(ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | head -1)}"
            if [ -n "$backup_file" ]; then
                COMPRESSED_BACKUP="$backup_file"
                verify_backup
            else
                log_error "No backup file specified or found"
                exit 1
            fi
            ;;
        "help")
            echo "Usage: $0 [action] [options]"
            echo
            echo "Actions:"
            echo "  backup/full  - Create full system backup (default)"
            echo "  database     - Backup database only"
            echo "  config       - Backup configuration only"
            echo "  restore      - Restore from backup file [backup_file]"
            echo "  list         - List available backups"
            echo "  cleanup      - Remove old backups"
            echo "  verify       - Verify backup integrity [backup_file]"
            echo "  help         - Show this help message"
            echo
            echo "Examples:"
            echo "  $0 backup"
            echo "  $0 restore ./backups/backup_20240115_120000.tar.gz"
            echo "  $0 list"
            echo "  $0 verify"
            ;;
        *)
            log_error "Unknown action: $action"
            echo "Use '$0 help' for usage information."
            exit 1
            ;;
    esac
}

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Execute main function
main "$@"