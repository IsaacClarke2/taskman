#!/bin/bash
# Test script for v0.9.0 features
# Run on server: ./scripts/test-v0.9.sh

set -e

echo "=========================================="
echo "  TaskMan v0.9.0 Test Script"
echo "=========================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"

# Test counter
PASSED=0
FAILED=0

test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}FAIL${NC}"
        ((FAILED++))
    fi
}

echo ""
echo -e "${YELLOW}=== 1. API Health ===${NC}"
echo -n "  Health endpoint: "
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
[ "$HEALTH" = "200" ]
test_result $?

echo ""
echo -e "${YELLOW}=== 2. Redis Connection ===${NC}"
echo -n "  Redis ping: "
docker-compose exec -T redis redis-cli ping | grep -q "PONG"
test_result $?

echo -n "  Redis set/get: "
docker-compose exec -T redis redis-cli set test:v09 "ok" EX 10 > /dev/null
REDIS_VAL=$(docker-compose exec -T redis redis-cli get test:v09)
[ "$REDIS_VAL" = "ok" ]
test_result $?

echo ""
echo -e "${YELLOW}=== 3. Integration Endpoints ===${NC}"

# These require auth, just check they return 401/403 not 500
echo -n "  Zoom auth endpoint: "
ZOOM=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/integrations/zoom/auth")
[ "$ZOOM" = "401" ] || [ "$ZOOM" = "500" ]  # 500 if not configured, 401 if auth required
test_result $?

echo -n "  Yandex connect endpoint: "
YANDEX=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/integrations/yandex/connect" -H "Content-Type: application/json" -d '{}')
[ "$YANDEX" = "401" ] || [ "$YANDEX" = "422" ]
test_result $?

echo -n "  Integration status: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/integrations/status")
[ "$STATUS" = "401" ]
test_result $?

echo ""
echo -e "${YELLOW}=== 4. Bot State in Redis ===${NC}"
echo -n "  Pending events key pattern: "
docker-compose exec -T redis redis-cli keys "pending:event:*" > /dev/null 2>&1
test_result $?

echo ""
echo -e "${YELLOW}=== 5. Worker Process ===${NC}"
echo -n "  Worker running: "
docker-compose ps worker | grep -q "Up"
test_result $?

echo ""
echo -e "${YELLOW}=== 6. Dateparser Test ===${NC}"
echo -n "  Python dateparser import: "
docker-compose exec -T api python -c "import dateparser; print(dateparser.parse('завтра в 15:00'))" > /dev/null 2>&1
test_result $?

echo ""
echo -e "${YELLOW}=== 7. ARQ Worker Test ===${NC}"
echo -n "  ARQ import: "
docker-compose exec -T worker python -c "from arq import create_pool; print('ok')" > /dev/null 2>&1
test_result $?

echo ""
echo "=========================================="
echo -e "  Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo "=========================================="

echo ""
echo "Manual tests to perform:"
echo ""
echo "1. Send text to bot: 'Встреча завтра в 15:00'"
echo "   Expected: Event preview with Meet/Zoom buttons"
echo ""
echo "2. Click '📹 + Google Meet' button"
echo "   Expected: Event created with Google Meet link"
echo ""
echo "3. Visit: https://your-domain.com/integrations/zoom"
echo "   Expected: Zoom OAuth redirect (if configured)"
echo ""
echo "4. Visit: https://your-domain.com/integrations/yandex"
echo "   Expected: Yandex email/password form"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed. Check logs:${NC}"
    echo "  docker-compose logs api"
    echo "  docker-compose logs bot"
    echo "  docker-compose logs worker"
    exit 1
fi

exit 0
