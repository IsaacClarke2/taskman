#!/bin/bash
#
# Telegram AI Business Assistant - Deployment Script
# Automatically sets up the application with free ports, Nginx, and SSL
#
set -e

# ============= Configuration =============

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/telegram-ai-assistant-deploy.log"
NGINX_CONF="/etc/nginx/sites-available/corben.pro"
NGINX_ENABLED="/etc/nginx/sites-enabled/corben.pro"

# Default values
DOMAIN="${DOMAIN:-corben.pro}"
EMAIL="${EMAIL:-}"
TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-}"
OPENAI_KEY="${OPENAI_KEY:-}"
INTERACTIVE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============= Logging Functions =============

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    case $level in
        INFO)  echo -e "${GREEN}[✓]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[!]${NC} $message" ;;
        ERROR) echo -e "${RED}[✗]${NC} $message" ;;
        STEP)  echo -e "${BLUE}[→]${NC} $message" ;;
    esac
}

# ============= Parse Arguments =============

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --domain=*)
                DOMAIN="${1#*=}"
                shift
                ;;
            --email=*)
                EMAIL="${1#*=}"
                shift
                ;;
            --telegram-token=*)
                TELEGRAM_TOKEN="${1#*=}"
                shift
                ;;
            --openai-key=*)
                OPENAI_KEY="${1#*=}"
                shift
                ;;
            --interactive|-i)
                INTERACTIVE=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log ERROR "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Telegram AI Business Assistant Deployment Script

OPTIONS:
    --domain=DOMAIN         Domain name (default: corben.pro)
    --email=EMAIL           Email for SSL certificate
    --telegram-token=TOKEN  Telegram bot token
    --openai-key=KEY        OpenAI API key
    --interactive, -i       Interactive mode (prompts for values)
    --help, -h              Show this help message

EXAMPLES:
    # Non-interactive deployment
    sudo bash deploy.sh \\
        --domain=corben.pro \\
        --email=admin@corben.pro \\
        --telegram-token=YOUR_TOKEN \\
        --openai-key=YOUR_KEY

    # Interactive deployment
    sudo bash deploy.sh --interactive

EOF
}

# ============= Dependency Checks =============

install_dependencies() {
    log STEP "Installing missing dependencies..."

    # Update package list (ignore GPG errors from third-party repos)
    apt-get update -qq 2>/dev/null || true

    # Install basic packages first (not docker - it may already be installed differently)
    apt-get install -y nginx certbot python3-certbot-nginx git openssl curl 2>&1 | tee -a "$LOG_FILE" || true

    # Check if Docker is already installed and working
    if command -v docker &> /dev/null && docker info &> /dev/null; then
        log INFO "Docker already installed and running"
    else
        # Try to install Docker
        if ! command -v docker &> /dev/null; then
            log STEP "Installing Docker..."
            # Try official Docker repo first, fallback to docker.io
            curl -fsSL https://get.docker.com | sh 2>&1 | tee -a "$LOG_FILE" || \
                apt-get install -y docker.io 2>&1 | tee -a "$LOG_FILE" || true
        fi
        # Start Docker
        systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
        systemctl enable docker 2>/dev/null || true
    fi

    # Install docker-compose (try multiple methods)
    if ! command -v docker-compose &> /dev/null; then
        log STEP "Installing docker-compose..."

        # Method 1: Try docker-compose-plugin (Docker Compose V2)
        if apt-get install -y docker-compose-plugin 2>/dev/null; then
            # Create wrapper script for docker-compose command
            if [ ! -f /usr/local/bin/docker-compose ]; then
                echo '#!/bin/bash' > /usr/local/bin/docker-compose
                echo 'docker compose "$@"' >> /usr/local/bin/docker-compose
                chmod +x /usr/local/bin/docker-compose
            fi
            log INFO "Installed docker-compose-plugin (V2)"
        # Method 2: Try apt package
        elif apt-get install -y docker-compose 2>/dev/null; then
            log INFO "Installed docker-compose from apt"
        # Method 3: Download binary directly
        else
            log STEP "Downloading docker-compose binary..."
            COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
            COMPOSE_VERSION=${COMPOSE_VERSION:-v2.24.0}
            curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose 2>&1 | tee -a "$LOG_FILE"
            chmod +x /usr/local/bin/docker-compose
            log INFO "Installed docker-compose ${COMPOSE_VERSION}"
        fi
    fi

    log INFO "Dependencies installed"
}

check_dependencies() {
    log STEP "[1/9] Checking dependencies..."

    # Check if running as root first
    if [ "$EUID" -ne 0 ]; then
        log ERROR "Please run as root (sudo)"
        exit 1
    fi

    local missing=()

    # Check required commands
    for cmd in docker docker-compose nginx certbot git openssl curl; do
        if ! command -v $cmd &> /dev/null; then
            missing+=($cmd)
        fi
    done

    # Auto-install if missing
    if [ ${#missing[@]} -gt 0 ]; then
        log WARN "Missing dependencies: ${missing[*]}"
        log STEP "Auto-installing dependencies..."
        install_dependencies

        # Re-check after installation
        for cmd in docker docker-compose nginx certbot git openssl; do
            if ! command -v $cmd &> /dev/null; then
                log ERROR "Failed to install: $cmd"
                exit 1
            fi
        done
    fi

    # Check Docker is running
    if ! docker info &> /dev/null; then
        log WARN "Docker is not running, starting..."
        systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
        sleep 3

        if ! docker info &> /dev/null; then
            log ERROR "Failed to start Docker"
            exit 1
        fi
    fi

    log INFO "All dependencies satisfied"
}

# ============= Port Management =============

find_free_port() {
    local start_port=$1
    local port=$start_port

    while true; do
        # Check if port is in use by any process
        if ss -tuln | grep -q ":$port "; then
            port=$((port + 1))
            continue
        fi

        # Check if port is used by Docker containers
        if docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$port->"; then
            port=$((port + 1))
            continue
        fi

        # Port is free
        echo $port
        return
    done
}

find_free_ports() {
    log STEP "[2/9] Finding free ports..."

    POSTGRES_PORT=$(find_free_port 5432)
    REDIS_PORT=$(find_free_port 6379)
    API_PORT=$(find_free_port 8000)
    WEB_PORT=$(find_free_port 3000)

    log INFO "PostgreSQL: $POSTGRES_PORT"
    log INFO "Redis: $REDIS_PORT"
    log INFO "API: $API_PORT"
    log INFO "Web: $WEB_PORT"
}

# ============= Environment Generation =============

prompt_if_missing() {
    local var_name=$1
    local prompt_text=$2
    local is_secret=${3:-false}

    local current_value="${!var_name}"

    if [ -z "$current_value" ] && [ "$INTERACTIVE" = true ]; then
        if [ "$is_secret" = true ]; then
            read -sp "$prompt_text: " value
            echo
        else
            read -p "$prompt_text: " value
        fi
        eval "$var_name='$value'"
    fi
}

generate_env() {
    log STEP "[3/9] Generating .env file..."

    # Prompt for missing values in interactive mode
    if [ "$INTERACTIVE" = true ]; then
        prompt_if_missing EMAIL "Enter email for SSL certificate"
        prompt_if_missing TELEGRAM_TOKEN "Enter Telegram bot token" true
        prompt_if_missing OPENAI_KEY "Enter OpenAI API key" true
    fi

    # Generate secure passwords
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9' | head -c 64)
    WEBHOOK_SECRET=$(openssl rand -hex 32)

    # Create .env file
    cat > "$SCRIPT_DIR/.env" << EOF
# ===========================================
# Telegram AI Business Assistant
# Generated by deploy.sh on $(date)
# ===========================================

# Database
POSTGRES_DB=assistant
POSTGRES_USER=assistant
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgresql+asyncpg://assistant:${POSTGRES_PASSWORD}@postgres:5432/assistant

# Ports (auto-selected)
POSTGRES_PORT=${POSTGRES_PORT}
REDIS_PORT=${REDIS_PORT}
API_PORT=${API_PORT}
WEB_PORT=${WEB_PORT}

# Redis
REDIS_URL=redis://redis:6379

# Telegram Bot
TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}
TELEGRAM_BOT_USERNAME=
TELEGRAM_WEBHOOK_SECRET=${WEBHOOK_SECRET}

# Web App
WEBAPP_URL=https://${DOMAIN}
DOMAIN=${DOMAIN}

# OpenAI
OPENAI_API_KEY=${OPENAI_KEY}

# Encryption
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# JWT
JWT_SECRET_KEY=${JWT_SECRET}

# Google OAuth (configure later)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Microsoft OAuth (configure later)
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# Notion OAuth (configure later)
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=

# Debug mode
DEBUG=false
EOF

    chmod 600 "$SCRIPT_DIR/.env"
    log INFO ".env file generated"
}

# ============= Docker Compose Update =============

update_docker_compose() {
    log STEP "[4/9] Updating docker-compose.yml with ports..."

    # Backup original
    cp "$SCRIPT_DIR/docker-compose.yml" "$SCRIPT_DIR/docker-compose.yml.bak"

    # Create new docker-compose with variable ports
    cat > "$SCRIPT_DIR/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: assistant-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-assistant}
      POSTGRES_USER: ${POSTGRES_USER:-assistant}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-assistant}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis for caching and job queues
  redis:
    image: redis:7-alpine
    container_name: assistant-redis
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # FastAPI Backend
  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    container_name: assistant-api
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-assistant}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-assistant}
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_WEBHOOK_SECRET=${TELEGRAM_WEBHOOK_SECRET}
      - WEBAPP_URL=${WEBAPP_URL}
      - DOMAIN=${DOMAIN}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - MICROSOFT_CLIENT_ID=${MICROSOFT_CLIENT_ID}
      - MICROSOFT_CLIENT_SECRET=${MICROSOFT_CLIENT_SECRET}
      - NOTION_CLIENT_ID=${NOTION_CLIENT_ID}
      - NOTION_CLIENT_SECRET=${NOTION_CLIENT_SECRET}
      - DEBUG=${DEBUG:-false}
    ports:
      - "${API_PORT:-8000}:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # Telegram Bot
  bot:
    build:
      context: .
      dockerfile: bot/Dockerfile
    container_name: assistant-bot
    environment:
      - API_URL=http://api:8000
      - REDIS_URL=redis://redis:6379
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - WEBAPP_URL=${WEBAPP_URL}
    depends_on:
      - api
      - redis
    restart: unless-stopped

  # Background Workers (arq)
  worker:
    build:
      context: .
      dockerfile: api/Dockerfile
    container_name: assistant-worker
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-assistant}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-assistant}
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: python -c "print('Worker placeholder - arq not configured yet')"
    restart: unless-stopped

  # Next.js Web App
  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: assistant-web
    environment:
      - NEXT_PUBLIC_API_URL=https://${DOMAIN}/api
      - NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME}
    ports:
      - "${WEB_PORT:-3000}:3000"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
EOF

    log INFO "docker-compose.yml updated"
}

# ============= Build and Run =============

build_and_run() {
    log STEP "[5/9] Building containers..."

    cd "$SCRIPT_DIR"

    # Load environment
    set -a
    source .env
    set +a

    # Build
    docker-compose build --no-cache 2>&1 | tee -a "$LOG_FILE"

    log STEP "[6/9] Starting containers..."
    docker-compose up -d 2>&1 | tee -a "$LOG_FILE"

    log INFO "Containers started"
}

# ============= Database Migrations =============

run_migrations() {
    log STEP "[7/9] Running database migrations..."

    # Wait for database to be ready
    sleep 5

    # Check if alembic is configured
    if [ -f "$SCRIPT_DIR/alembic.ini" ]; then
        docker-compose exec -T api alembic upgrade head 2>&1 | tee -a "$LOG_FILE" || true
    else
        log WARN "Alembic not configured yet - skipping migrations"
    fi

    log INFO "Database ready"
}

# ============= Nginx Configuration =============

setup_nginx() {
    log STEP "[8/9] Setting up Nginx..."

    # Load ports from .env
    source "$SCRIPT_DIR/.env"

    # Create Nginx config
    cat > "$NGINX_CONF" << EOF
# Telegram AI Business Assistant
# Generated by deploy.sh

# HTTP redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};

    # SSL certificates (will be created by certbot)
    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend (Next.js)
    location / {
        proxy_pass http://127.0.0.1:${WEB_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 86400;
    }

    # API
    location /api/ {
        rewrite ^/api/(.*)\$ /\$1 break;
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
    }

    # Telegram Webhook
    location /telegram/webhook {
        proxy_pass http://127.0.0.1:${API_PORT}/telegram/webhook;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    # Enable site
    ln -sf "$NGINX_CONF" "$NGINX_ENABLED" 2>/dev/null || true

    # Test Nginx config (ignore SSL errors for now)
    nginx -t 2>&1 | grep -v "ssl_certificate" || true

    log INFO "Nginx configured"
}

# ============= SSL Certificate =============

setup_ssl() {
    log STEP "[9/9] Setting up SSL certificate..."

    if [ -z "$EMAIL" ]; then
        log WARN "Email not provided - skipping SSL setup"
        log WARN "Run manually: certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
        return
    fi

    # Create webroot directory
    mkdir -p /var/www/certbot

    # Check if certificate already exists
    if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
        log INFO "SSL certificate already exists"
    else
        # Get certificate
        certbot certonly --webroot -w /var/www/certbot \
            -d "${DOMAIN}" -d "www.${DOMAIN}" \
            --non-interactive --agree-tos -m "${EMAIL}" \
            2>&1 | tee -a "$LOG_FILE" || {
            log WARN "Certbot webroot failed, trying nginx plugin..."
            certbot --nginx -d "${DOMAIN}" -d "www.${DOMAIN}" \
                --non-interactive --agree-tos -m "${EMAIL}" \
                2>&1 | tee -a "$LOG_FILE" || {
                log ERROR "SSL certificate generation failed"
                log WARN "You can try manually: certbot --nginx -d ${DOMAIN}"
            }
        }
    fi

    # Reload Nginx
    nginx -s reload 2>/dev/null || systemctl reload nginx || true

    log INFO "SSL setup complete"
}

# ============= Health Check =============

healthcheck() {
    echo ""
    echo -e "${BLUE}=== Healthcheck ===${NC}"

    # Wait for services to start
    sleep 10

    # Load ports
    source "$SCRIPT_DIR/.env"

    local all_ok=true

    # Check PostgreSQL
    if docker-compose exec -T postgres pg_isready -U assistant > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL: OK${NC}"
    else
        echo -e "${RED}❌ PostgreSQL: FAILED${NC}"
        docker-compose logs --tail=20 postgres
        all_ok=false
    fi

    # Check Redis
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis: OK${NC}"
    else
        echo -e "${RED}❌ Redis: FAILED${NC}"
        docker-compose logs --tail=20 redis
        all_ok=false
    fi

    # Check API
    sleep 5
    if curl -sf "http://127.0.0.1:${API_PORT}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ API: OK${NC}"
    else
        echo -e "${RED}❌ API: FAILED${NC}"
        docker-compose logs --tail=30 api
        all_ok=false
    fi

    # Check Web
    if curl -sf "http://127.0.0.1:${WEB_PORT}" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Web: OK${NC}"
    else
        echo -e "${YELLOW}⚠️  Web: Not ready (may need npm build)${NC}"
    fi

    # Check HTTPS (if certificate exists)
    if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
        if curl -sf "https://${DOMAIN}/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ HTTPS: OK${NC}"
        else
            echo -e "${YELLOW}⚠️  HTTPS: Check Nginx config${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  HTTPS: Certificate not installed${NC}"
    fi

    echo ""

    if [ "$all_ok" = false ]; then
        log WARN "Some services failed - check logs above"
    fi
}

# ============= Summary =============

print_summary() {
    source "$SCRIPT_DIR/.env"

    echo ""
    echo -e "${GREEN}=== Deployment Complete ===${NC}"
    echo ""
    echo -e "Frontend:         ${BLUE}https://${DOMAIN}${NC}"
    echo -e "API:              ${BLUE}https://${DOMAIN}/api${NC}"
    echo -e "Telegram Webhook: ${BLUE}https://${DOMAIN}/telegram/webhook${NC}"
    echo ""
    echo "Ports used:"
    echo "  - PostgreSQL: ${POSTGRES_PORT}"
    echo "  - Redis:      ${REDIS_PORT}"
    echo "  - API:        ${API_PORT}"
    echo "  - Web:        ${WEB_PORT}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Configure OAuth credentials in .env:"
    echo "   - GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET"
    echo "   - MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET"
    echo "   - NOTION_CLIENT_ID / NOTION_CLIENT_SECRET"
    echo ""
    echo "2. Set up Telegram webhook:"
    echo "   curl -X POST 'https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/setWebhook' \\"
    echo "     -d 'url=https://${DOMAIN}/telegram/webhook' \\"
    echo "     -d 'secret_token=\${TELEGRAM_WEBHOOK_SECRET}'"
    echo ""
    echo "3. Restart after changes:"
    echo "   cd $SCRIPT_DIR && docker-compose restart"
    echo ""
    echo -e "Log file: ${LOG_FILE}"
    echo ""
}

# ============= Rollback =============

rollback() {
    log WARN "Rolling back changes..."

    # Stop containers
    cd "$SCRIPT_DIR"
    docker-compose down 2>/dev/null || true

    # Restore docker-compose backup
    if [ -f "$SCRIPT_DIR/docker-compose.yml.bak" ]; then
        mv "$SCRIPT_DIR/docker-compose.yml.bak" "$SCRIPT_DIR/docker-compose.yml"
    fi

    # Remove Nginx config
    rm -f "$NGINX_ENABLED" 2>/dev/null || true
    rm -f "$NGINX_CONF" 2>/dev/null || true
    nginx -s reload 2>/dev/null || true

    log INFO "Rollback complete"
}

# ============= Main =============

main() {
    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"

    echo ""
    echo -e "${GREEN}=== Telegram AI Business Assistant Deployment ===${NC}"
    echo ""

    # Set up error handling
    trap rollback ERR

    parse_args "$@"
    check_dependencies
    find_free_ports
    generate_env
    update_docker_compose
    build_and_run
    run_migrations
    setup_nginx
    setup_ssl
    healthcheck
    print_summary

    # Remove trap on success
    trap - ERR
}

# Run
main "$@"
