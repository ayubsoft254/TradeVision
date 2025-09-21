# TradeVision Deployment Makefile
# Usage: make [target]

# Variables
COMPOSE_FILE = docker-compose.yml
ENV_FILE = .env
BACKUP_DIR = ./backups

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help deploy status logs backup restore clean setup check health restart stop start

# Default target
help:
	@echo "TradeVision Deployment Commands"
	@echo "==============================="
	@echo
	@echo "Setup & Deployment:"
	@echo "  setup     - Initial setup (copy .env, create directories)"
	@echo "  deploy    - Deploy application (full deployment)"
	@echo "  start     - Start all services"
	@echo "  stop      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo	
	@echo "  app-restart  - Restart app services only (keeps DB running)"
	@echo "  app-redeploy - Rebuild and restart app services"  
	@echo "  web-restart  - Restart web service only (fastest)"
	@echo "  web-redeploy - Rebuild and restart web service"
	@echo
	@echo "Monitoring:"
	@echo "  status    - Show service status"
	@echo "  health    - Health check all services"
	@echo "  logs      - Show logs [SERVICE=service_name] [LINES=50]"
	@echo "  monitor   - Run continuous monitoring"
	@echo
	@echo "Maintenance:"
	@echo "  backup    - Create full backup"
	@echo "  restore   - Restore from backup [BACKUP=backup_file]"
	@echo "  clean     - Clean up containers and images"
	@echo "  check     - Run system checks"
	@echo
	@echo "Development:"
	@echo "  shell     - Open shell [SERVICE=web]"
	@echo "  django    - Run Django management commands [CMD=command]"
	@echo "  flower    - Start Flower monitoring"
	@echo
	
	@echo "Examples:"
	@echo "  make deploy"
	@echo "  make logs SERVICE=celery_worker_critical LINES=100"
	@echo "  make backup"
	@echo "  make django CMD='migrate'"

	

# Setup commands
setup:
	@echo -e "$(GREEN)Setting up TradeVision...$(NC)"
	@if [ ! -f $(ENV_FILE) ]; then \
		cp .env.example $(ENV_FILE); \
		echo -e "$(YELLOW)Created .env file from .env.example$(NC)"; \
		echo -e "$(RED)Please edit .env file with your configuration!$(NC)"; \
	else \
		echo -e "$(GREEN).env file already exists$(NC)"; \
	fi
	@mkdir -p $(BACKUP_DIR) logs scripts
	@chmod +x scripts/*.sh
	@echo -e "$(GREEN)Setup completed!$(NC)"

check:
	@echo -e "$(GREEN)Running system checks...$(NC)"
	@./scripts/wait-for-it.sh localhost 7373 5 || echo -e "$(YELLOW)Application not running$(NC)"
	@docker --version || (echo -e "$(RED)Docker not installed$(NC)" && exit 1)
	@docker-compose --version || (echo -e "$(RED)Docker Compose not installed$(NC)" && exit 1)
	@test -f $(ENV_FILE) || (echo -e "$(RED).env file missing$(NC)" && exit 1)
	@echo -e "$(GREEN)System checks passed$(NC)"

# Deployment commands
deploy:
	@echo -e "$(GREEN)Deploying TradeVision...$(NC)"
	@./scripts/deploy.sh deploy

start:
	@echo -e "$(GREEN)Starting TradeVision services...$(NC)"
	@docker-compose up -d
	@echo -e "$(GREEN)Services started$(NC)"

stop:
	@echo -e "$(YELLOW)Stopping TradeVision services...$(NC)"
	@docker-compose down
	@echo -e "$(YELLOW)Services stopped$(NC)"

restart:
	@echo -e "$(YELLOW)Restarting TradeVision services...$(NC)"
	@docker-compose restart
	@echo -e "$(GREEN)Services restarted$(NC)"

# Restart only application services (keeps DB and persistent services running)
app-restart:
	@echo -e "$(YELLOW)Restarting application services (keeping DB services running)...$(NC)"
	@docker-compose restart web celery_worker_critical celery_worker_general celery_beat  redis
	@echo -e "$(GREEN)Application services restarted$(NC)"

# Alternative version that rebuilds the web service for code changes
app-redeploy:
	@echo -e "$(YELLOW)Redeploying application with fresh build...$(NC)"
	@docker-compose build web
	@docker-compose up -d --no-deps web celery_worker_critical celery_worker_general celery_beat
	@echo -e "$(GREEN)Application redeployed$(NC)"

# Restart only web service (fastest for template updates)
web-restart:
	@echo -e "$(YELLOW)Restarting web service only...$(NC)"
	@docker-compose restart web
	@echo -e "$(GREEN)Web service restarted$(NC)"

# Restart web service with rebuild (for code changes)
web-redeploy:
	@echo -e "$(YELLOW)Rebuilding and restarting web service...$(NC)"
	@docker-compose build web
	@docker-compose up -d --no-deps web
	@echo -e "$(GREEN)Web service rebuilt and restarted$(NC)"

# Safe redeploy - rebuilds everything except database services
safe-redeploy:
	@echo -e "$(YELLOW)Starting safe redeploy (preserving database)...$(NC)"
	@echo -e "$(GREEN)Creating backup before redeploy...$(NC)"
	@./scripts/backup.sh backup || echo -e "$(YELLOW)Backup script not available, continuing...$(NC)"
	@echo -e "$(YELLOW)Stopping application services (keeping DB running)...$(NC)"
	@docker-compose stop web celery_worker_critical celery_worker_general celery_beat redis flower || true
	@echo -e "$(YELLOW)Pulling latest images...$(NC)"
	@docker-compose pull web redis
	@echo -e "$(YELLOW)Rebuilding application containers...$(NC)"
	@docker-compose build --no-cache web
	@echo -e "$(YELLOW)Starting services with fresh containers...$(NC)"
	@docker-compose up -d --force-recreate web celery_worker_critical celery_worker_general celery_beat redis
	@echo -e "$(GREEN)Running migrations (safe)...$(NC)"
	@docker-compose exec web python manage.py migrate --noinput
	@echo -e "$(GREEN)Collecting static files...$(NC)"
	@docker-compose exec web python manage.py collectstatic --noinput --clear
	@echo -e "$(GREEN)Safe redeploy completed! Database preserved.$(NC)"

# Full redeploy with backup - safest option
full-redeploy:
	@echo -e "$(YELLOW)Starting full redeploy with backup...$(NC)"
	@echo -e "$(GREEN)Creating full backup...$(NC)"
	@./scripts/backup.sh backup
	@echo -e "$(YELLOW)Stopping all application services...$(NC)"
	@docker-compose stop web celery_worker_critical celery_worker_general celery_beat redis flower || true
	@echo -e "$(YELLOW)Removing old containers (keeping volumes)...$(NC)"
	@docker-compose rm -f web celery_worker_critical celery_worker_general celery_beat redis flower || true
	@echo -e "$(YELLOW)Pulling latest images...$(NC)"
	@docker-compose pull
	@echo -e "$(YELLOW)Building fresh containers...$(NC)"
	@docker-compose build --no-cache
	@echo -e "$(YELLOW)Starting services with fresh containers...$(NC)"
	@docker-compose up -d --force-recreate
	@echo -e "$(GREEN)Running health checks...$(NC)"
	@sleep 10
	@./scripts/monitor.sh monitor || echo -e "$(YELLOW)Health check script not available$(NC)"
	@echo -e "$(GREEN)Full redeploy completed! Database preserved.$(NC)"

# Quick rebuild - fastest option for code changes
quick-rebuild:
	@echo -e "$(YELLOW)Quick rebuild of application...$(NC)"
	@docker-compose build web
	@docker-compose up -d --no-deps --force-recreate web celery_worker_critical celery_worker_general celery_beat
	@echo -e "$(GREEN)Quick rebuild completed$(NC)"

# Deploy with git pull - for production updates
deploy-update:
	@echo -e "$(GREEN)Deploying latest code...$(NC)"
	@echo -e "$(YELLOW)Creating backup...$(NC)"
	@./scripts/backup.sh backup || echo -e "$(YELLOW)Backup skipped$(NC)"
	@echo -e "$(YELLOW)Pulling latest code...$(NC)"
	@git pull origin main || echo -e "$(YELLOW)Git pull skipped$(NC)"
	@echo -e "$(YELLOW)Rebuilding with latest code...$(NC)"
	@docker-compose build --pull web
	@docker-compose stop web celery_worker_critical celery_worker_general celery_beat
	@docker-compose up -d --force-recreate web celery_worker_critical celery_worker_general celery_beat
	@echo -e "$(GREEN)Running migrations...$(NC)"
	@docker-compose exec web python manage.py migrate --noinput
	@echo -e "$(GREEN)Collecting static files...$(NC)"
	@docker-compose exec web python manage.py collectstatic --noinput --clear
	@echo -e "$(GREEN)Update deployment completed$(NC)"

# Zero-downtime redeploy (advanced)
zero-downtime-redeploy:
	@echo -e "$(GREEN)Starting zero-downtime redeploy...$(NC)"
	@echo -e "$(YELLOW)Creating backup...$(NC)"
	@./scripts/backup.sh backup || true
	@echo -e "$(YELLOW)Building new containers...$(NC)"
	@docker-compose build web
	@echo -e "$(YELLOW)Starting new web container alongside old one...$(NC)"
	@docker-compose up -d --no-deps --scale web=2 web
	@echo -e "$(YELLOW)Waiting for new container to be ready...$(NC)"
	@sleep 15
	@echo -e "$(YELLOW)Scaling down to single container...$(NC)"
	@docker-compose up -d --no-deps --scale web=1 --force-recreate web
	@echo -e "$(YELLOW)Updating worker services...$(NC)"
	@docker-compose up -d --no-deps --force-recreate celery_worker_critical celery_worker_general celery_beat
	@echo -e "$(GREEN)Zero-downtime redeploy completed$(NC)"

# Emergency rollback (if something goes wrong)
rollback:
	@if [ -z "$(BACKUP)" ]; then \
		echo -e "$(RED)Please specify backup file: make rollback BACKUP=backup_file$(NC)"; \
		echo -e "$(YELLOW)Available backups:$(NC)"; \
		ls -la $(BACKUP_DIR)/ | tail -5; \
		exit 1; \
	fi
	@echo -e "$(RED)EMERGENCY ROLLBACK - Rolling back to $(BACKUP)...$(NC)"
	@docker-compose stop web celery_worker_critical celery_worker_general celery_beat
	@./scripts/backup.sh restore $(BACKUP)
	@docker-compose up -d
	@echo -e "$(GREEN)Rollback completed$(NC)"

# Monitoring commands
status:
	@echo -e "$(GREEN)TradeVision Service Status:$(NC)"
	@docker-compose ps
	@echo
	@echo -e "$(GREEN)Resource Usage:$(NC)"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -10

health:
	@echo -e "$(GREEN)Running health checks...$(NC)"
	@./scripts/monitor.sh monitor

logs:
	@echo -e "$(GREEN)Showing logs for $(or $(SERVICE),web)...$(NC)"
	@docker-compose logs --tail=$(or $(LINES),50) -f $(or $(SERVICE),web)

monitor:
	@echo -e "$(GREEN)Starting continuous monitoring...$(NC)"
	@./scripts/monitor.sh continuous

# Maintenance commands
backup:
	@echo -e "$(GREEN)Creating backup...$(NC)"
	@./scripts/backup.sh backup

restore:
	@if [ -z "$(BACKUP)" ]; then \
		echo -e "$(RED)Please specify backup file: make restore BACKUP=backup_file$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(YELLOW)Restoring from $(BACKUP)...$(NC)"
	@./scripts/backup.sh restore $(BACKUP)

clean:
	@echo -e "$(YELLOW)Cleaning up containers and images...$(NC)"
	@docker-compose down --remove-orphans
	@docker container prune -f
	@docker image prune -f
	@docker volume prune -f
	@echo -e "$(GREEN)Cleanup completed$(NC)"

# Development commands
shell:
	@echo -e "$(GREEN)Opening shell in $(or $(SERVICE),web) container...$(NC)"
	@docker-compose exec $(or $(SERVICE),web) /bin/bash

django:
	@if [ -z "$(CMD)" ]; then \
		echo -e "$(RED)Please specify Django command: make django CMD='migrate'$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(GREEN)Running Django command: $(CMD)$(NC)"
	@docker-compose exec web python manage.py $(CMD)

flower:
	@echo -e "$(GREEN)Starting Flower monitoring...$(NC)"
	@docker-compose --profile monitoring up -d flower
	@echo -e "$(GREEN)Flower available at: http://localhost:5555$(NC)"

# Database commands
db-shell:
	@echo -e "$(GREEN)Opening database shell...$(NC)"
	@docker-compose exec db psql -U tradevision -d tradevision

db-backup:
	@echo -e "$(GREEN)Creating database backup...$(NC)"
	@./scripts/backup.sh database

# Advanced commands
rebuild:
	@echo -e "$(YELLOW)Rebuilding application...$(NC)"
	@docker-compose build --no-cache
	@docker-compose up -d --force-recreate
	@echo -e "$(GREEN)Rebuild completed$(NC)"

update:
	@echo -e "$(GREEN)Updating TradeVision...$(NC)"
	@git pull origin main || echo -e "$(YELLOW)Git pull skipped$(NC)"
	@docker-compose pull
	@docker-compose build --pull
	@./scripts/deploy.sh deploy
	@echo -e "$(GREEN)Update completed$(NC)"

reset:
	@echo -e "$(RED)WARNING: This will destroy all data!$(NC)"
	@read -p "Are you sure? (yes/no): " -r REPLY; \
	if [ "$$REPLY" = "yes" ]; then \
		docker-compose down -v --remove-orphans; \
		docker volume rm tradevision_postgres_data tradevision_redis_data tradevision_media_volume tradevision_static_volume tradevision_logs_volume 2>/dev/null || true; \
		echo -e "$(YELLOW)All data destroyed$(NC)"; \
	else \
		echo -e "$(GREEN)Reset cancelled$(NC)"; \
	fi

# SSL certificate renewal (if using Let's Encrypt)
renew-ssl:
	@echo -e "$(GREEN)Renewing SSL certificates...$(NC)"
	@sudo certbot renew --quiet
	@sudo systemctl reload nginx
	@echo -e "$(GREEN)SSL certificates renewed$(NC)"

# Performance optimization
optimize:
	@echo -e "$(GREEN)Optimizing system performance...$(NC)"
	@docker system prune -f
	@sudo sysctl vm.max_map_count=262144 || echo "Could not optimize vm.max_map_count"
	@echo -e "$(GREEN)Optimization completed$(NC)"

# Security scan
security-scan:
	@echo -e "$(GREEN)Running security scan...$(NC)"
	@docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
		-v $(PWD):/src aquasec/trivy fs --security-checks vuln /src || echo -e "$(YELLOW)Security scan completed with warnings$(NC)"

# Load testing
load-test:
	@echo -e "$(GREEN)Running load test...$(NC)"
	@if command -v ab >/dev/null 2>&1; then \
		ab -n 1000 -c 10 https://tradevision.uk/health/; \
	else \
		echo -e "$(YELLOW)Apache Bench (ab) not installed. Install with: sudo apt-get install apache2-utils$(NC)"; \
	fi

# Development environment
dev-setup:
	@echo -e "$(GREEN)Setting up development environment...$(NC)"
	@cp .env.example .env.dev
	@sed -i 's/DEBUG=0/DEBUG=1/g' .env.dev
	@sed -i 's/SECURE_SSL_REDIRECT=True/SECURE_SSL_REDIRECT=False/g' .env.dev
	@echo -e "$(GREEN)Development environment configured$(NC)"
	@echo -e "$(YELLOW)Use: docker-compose --env-file .env.dev up -d$(NC)"

# Quick commands for common operations
quick-deploy: backup deploy health
	@echo -e "$(GREEN)Quick deployment completed!$(NC)"

quick-restart: backup stop start health
	@echo -e "$(GREEN)Quick restart completed!$(NC)"

# Show resource usage
resources:
	@echo -e "$(GREEN)System Resource Usage:$(NC)"
	@echo "Disk Usage:"
	@df -h / | awk 'NR==2{printf "  Root: %s used, %s available (%s)\n", $$3, $$4, $$5}'
	@echo "Memory Usage:"
	@free -h | awk 'NR==2{printf "  RAM: %s used, %s available\n", $$3, $$7}'
	@echo "Docker Usage:"
	@docker system df
	@echo "Container Stats:"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | head -10
