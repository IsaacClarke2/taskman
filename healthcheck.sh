#!/bin/bash
#
# Modular Health Check Script
# Check each service independently and report status
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# Default ports
API_PORT=${API_PORT:-8000}
WEB_PORT=${WEB_PORT:-3000}
DOMAIN=${DOMAIN:-corben.pro}

# ============= Individual Checks =============

check_postgres() {
    echo -n "PostgreSQL: "
    if docker-compose exec -T postgres pg_isready -U assistant > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        return 1
    fi
}

check_redis() {
    echo -n "Redis: "
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        return 1
    fi
}

check_api() {
    echo -n "API: "
    if curl -sf "http://127.0.0.1:${API_PORT}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        return 1
    fi
}

check_bot() {
    echo -n "Bot: "
    local status=$(docker-compose ps -q bot 2>/dev/null)
    if [ -n "$status" ]; then
        local running=$(docker inspect -f '{{.State.Running}}' assistant-bot 2>/dev/null)
        if [ "$running" = "true" ]; then
            echo -e "${GREEN}OK${NC}"
            return 0
        fi
    fi
    echo -e "${RED}FAILED${NC}"
    return 1
}

check_web() {
    echo -n "Web: "
    if curl -sf "http://127.0.0.1:${WEB_PORT}" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}NOT READY${NC}"
        return 1
    fi
}

check_https() {
    echo -n "HTTPS: "
    if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
        if curl -sf "https://${DOMAIN}/health" > /dev/null 2>&1; then
            echo -e "${GREEN}OK${NC}"
            return 0
        else
            echo -e "${YELLOW}CHECK NGINX${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}NO CERT${NC}"
        return 1
    fi
}

# ============= Service Management =============

show_logs() {
    local service=$1
    local lines=${2:-50}
    echo -e "${BLUE}=== Logs for $service (last $lines lines) ===${NC}"
    docker-compose logs --tail=$lines $service
}

restart_service() {
    local service=$1
    echo -e "${BLUE}Restarting $service...${NC}"
    docker-compose restart $service
    echo -e "${GREEN}Done${NC}"
}

rebuild_service() {
    local service=$1
    echo -e "${BLUE}Rebuilding $service...${NC}"
    docker-compose build --no-cache $service
    docker-compose up -d $service
    echo -e "${GREEN}Done${NC}"
}

# ============= Main =============

show_help() {
    cat << EOF
Modular Health Check Script

Usage: $0 [command] [service]

Commands:
    check       Run all health checks (default)
    logs        Show logs for a service
    restart     Restart a service
    rebuild     Rebuild and restart a service
    status      Show container status

Services: postgres, redis, api, bot, web, worker

Examples:
    $0                      # Check all services
    $0 check api            # Check only API
    $0 logs bot             # Show bot logs
    $0 restart api          # Restart API
    $0 rebuild bot          # Rebuild and restart bot

EOF
}

main() {
    cd "$SCRIPT_DIR"

    local command=${1:-check}
    local service=${2:-all}

    case $command in
        check)
            echo -e "${BLUE}=== Health Check ===${NC}"
            if [ "$service" = "all" ]; then
                check_postgres || true
                check_redis || true
                check_api || true
                check_bot || true
                check_web || true
                check_https || true
            else
                check_$service || echo "Unknown service: $service"
            fi
            ;;
        logs)
            if [ "$service" = "all" ]; then
                docker-compose logs --tail=20
            else
                show_logs $service ${3:-50}
            fi
            ;;
        restart)
            if [ "$service" = "all" ]; then
                docker-compose restart
            else
                restart_service $service
            fi
            ;;
        rebuild)
            if [ -z "$service" ] || [ "$service" = "all" ]; then
                echo "Please specify a service to rebuild"
                exit 1
            fi
            rebuild_service $service
            ;;
        status)
            docker-compose ps
            ;;
        -h|--help|help)
            show_help
            ;;
        *)
            echo "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
