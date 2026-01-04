#!/bin/bash
# Update script for v0.9.0 - Optimization + New Integrations
# Run on server: ./scripts/update-v0.9.sh

set -e

echo "=========================================="
echo "  TaskMan v0.9.0 Update Script"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: Run this script from project root${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 1: Pull latest changes${NC}"
git pull origin main

echo ""
echo -e "${YELLOW}Step 2: Check .env for new variables${NC}"
ENV_FILE=".env"
REQUIRED_VARS=(
    "REDIS_URL"
    "ZOOM_CLIENT_ID"
    "ZOOM_CLIENT_SECRET"
    "OPENAI_API_KEY"
)

MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
        MISSING+=("$var")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${YELLOW}Missing environment variables:${NC}"
    for var in "${MISSING[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Add them to .env:"
    echo "  REDIS_URL=redis://redis:6379/0"
    echo "  ZOOM_CLIENT_ID=your_zoom_client_id"
    echo "  ZOOM_CLIENT_SECRET=your_zoom_client_secret"
    echo "  OPENAI_API_KEY=your_openai_key"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}Step 3: Rebuild and restart services${NC}"
docker-compose build --no-cache api bot worker
docker-compose up -d api bot worker web

echo ""
echo -e "${YELLOW}Step 4: Wait for services to start${NC}"
sleep 10

echo ""
echo -e "${YELLOW}Step 5: Health checks${NC}"

# Check API
echo -n "  API: "
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Redis
echo -n "  Redis: "
if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Bot
echo -n "  Bot: "
if docker-compose logs --tail=5 bot 2>&1 | grep -q "Starting bot"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}Check logs${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "  Update complete!"
echo "==========================================${NC}"
echo ""
echo "New features available:"
echo "  - Local date parsing (reduces API costs)"
echo "  - Redis state storage (bot)"
echo "  - Zoom integration (/integrations/zoom)"
echo "  - Yandex Calendar (/integrations/yandex)"
echo "  - Google Meet button in bot"
echo ""
echo "Test commands:"
echo "  ./scripts/test-v0.9.sh"
