# Deployment Instructions

Инструкция для деплоя на production-сервер.

---

## Требования к серверу

- Ubuntu 22.04+ или Debian 12+
- Docker и Docker Compose установлены
- Nginx установлен (для reverse proxy)
- Certbot установлен (для SSL)
- Git установлен
- На сервере уже работают другие сервисы и Docker-контейнеры — **нельзя их задеть**

---

## Домен

- **Frontend:** `corben.pro`
- **API:** `api.corben.pro` (или `corben.pro/api`)
- **Telegram Webhook:** `api.corben.pro/telegram/webhook`

**Важно:** Telegram Login Widget требует HTTPS. Без SSL авторизация работать не будет.

---

## Что должен сделать деплой-скрипт

### 1. Клонирование репозитория

```bash
git clone https://github.com/{USERNAME}/{REPO}.git /opt/telegram-ai-assistant
cd /opt/telegram-ai-assistant
```

### 2. Автоматический выбор свободных портов

Скрипт должен:
1. Найти 4 свободных порта (PostgreSQL, Redis, API, Web)
2. Проверить что порты не заняты другими процессами
3. Проверить что порты не используются другими Docker-контейнерами
4. Записать выбранные порты в `.env`

**Алгоритм поиска свободного порта:**
```bash
find_free_port() {
    local port=$1
    while ss -tuln | grep -q ":$port " || docker ps --format '{{.Ports}}' | grep -q ":$port->"; do
        port=$((port + 1))
    done
    echo $port
}

POSTGRES_PORT=$(find_free_port 5432)
REDIS_PORT=$(find_free_port 6379)
API_PORT=$(find_free_port 8000)
WEB_PORT=$(find_free_port 3000)
```

### 3. Генерация .env файла

Скрипт должен:
1. Скопировать `.env.example` в `.env`
2. Сгенерировать случайные пароли для PostgreSQL
3. Сгенерировать `ENCRYPTION_KEY`
4. Подставить выбранные порты
5. Запросить у пользователя или взять из аргументов:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - OAuth credentials (можно оставить пустыми для первого запуска)

### 4. Обновление docker-compose.yml

Заменить захардкоженные порты на переменные из `.env`:
```yaml
ports:
  - "${POSTGRES_PORT}:5432"
  - "${REDIS_PORT}:6379"
  - "${API_PORT}:8000"
  - "${WEB_PORT}:3000"
```

### 5. Сборка и запуск контейнеров

```bash
docker-compose build --no-cache
docker-compose up -d
```

### 6. Применение миграций БД

```bash
docker-compose exec -T api alembic upgrade head
```

### 7. Настройка Nginx + SSL

**Nginx конфиг для corben.pro:**

```nginx
# /etc/nginx/sites-available/corben.pro

# Frontend
server {
    listen 80;
    server_name corben.pro www.corben.pro;
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name corben.pro www.corben.pro;

    ssl_certificate /etc/letsencrypt/live/corben.pro/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/corben.pro/privkey.pem;
    
    # Frontend (Next.js)
    location / {
        proxy_pass http://127.0.0.1:${WEB_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # API
    location /api/ {
        proxy_pass http://127.0.0.1:${API_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Telegram Webhook
    location /telegram/webhook {
        proxy_pass http://127.0.0.1:${API_PORT}/telegram/webhook;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**SSL через Certbot:**
```bash
certbot --nginx -d corben.pro -d www.corben.pro --non-interactive --agree-tos -m {EMAIL}
```

### 8. Healthcheck и логирование

После запуска скрипт должен:
1. Подождать 30 секунд для старта контейнеров
2. Проверить health каждого сервиса
3. Вывести статус
4. При ошибках — показать логи

```bash
echo "=== Checking services ==="

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U assistant > /dev/null 2>&1; then
    echo "✅ PostgreSQL: OK"
else
    echo "❌ PostgreSQL: FAILED"
    docker-compose logs --tail=50 postgres
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: OK"
else
    echo "❌ Redis: FAILED"
    docker-compose logs --tail=50 redis
fi

# Check API
if curl -s http://127.0.0.1:${API_PORT}/health > /dev/null 2>&1; then
    echo "✅ API: OK"
else
    echo "❌ API: FAILED"
    docker-compose logs --tail=50 api
fi

# Check Web
if curl -s http://127.0.0.1:${WEB_PORT} > /dev/null 2>&1; then
    echo "✅ Web: OK"
else
    echo "❌ Web: FAILED"
    docker-compose logs --tail=50 web
fi

# Check HTTPS
if curl -s https://corben.pro > /dev/null 2>&1; then
    echo "✅ HTTPS: OK"
else
    echo "❌ HTTPS: FAILED — check nginx and certbot"
fi
```

---

## Структура деплой-скрипта

Создай файл `deploy.sh` в корне проекта:

```bash
#!/bin/bash
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Telegram AI Assistant Deployment ===${NC}"

# 1. Проверка зависимостей
check_dependencies() { ... }

# 2. Поиск свободных портов
find_free_ports() { ... }

# 3. Генерация .env
generate_env() { ... }

# 4. Обновление docker-compose.yml с портами
update_docker_compose() { ... }

# 5. Сборка и запуск
build_and_run() { ... }

# 6. Миграции БД
run_migrations() { ... }

# 7. Настройка Nginx
setup_nginx() { ... }

# 8. SSL сертификат
setup_ssl() { ... }

# 9. Healthcheck
healthcheck() { ... }

# 10. Вывод итоговой информации
print_summary() { ... }

# Запуск
main() {
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
}

main "$@"
```

---

## Ожидаемый результат

После запуска `deploy.sh` пользователь должен получить:

```
=== Telegram AI Assistant Deployment ===

[1/9] Checking dependencies... ✅
[2/9] Finding free ports...
  - PostgreSQL: 5433
  - Redis: 6380
  - API: 8001
  - Web: 3001
[3/9] Generating .env... ✅
[4/9] Updating docker-compose.yml... ✅
[5/9] Building containers... ✅
[6/9] Starting containers... ✅
[7/9] Running migrations... ✅
[8/9] Setting up Nginx... ✅
[9/9] Setting up SSL... ✅

=== Healthcheck ===
✅ PostgreSQL: OK
✅ Redis: OK
✅ API: OK
✅ Web: OK
✅ HTTPS: OK

=== Deployment Complete ===

Frontend: https://corben.pro
API: https://corben.pro/api
Telegram Webhook: https://corben.pro/api/telegram/webhook

Ports used:
  - PostgreSQL: 5433
  - Redis: 6380
  - API: 8001
  - Web: 3001

Next steps:
1. Set TELEGRAM_BOT_TOKEN in .env
2. Set OPENAI_API_KEY in .env
3. Configure OAuth credentials
4. Run: docker-compose restart
```

---

## Команды для пользователя

**Загрузка и запуск:**
```bash
# Клонирование
git clone https://github.com/{USERNAME}/telegram-ai-assistant.git /opt/telegram-ai-assistant

# Переход в директорию
cd /opt/telegram-ai-assistant

# Запуск деплоя (от root или с sudo)
sudo bash deploy.sh \
  --domain=corben.pro \
  --email=your@email.com \
  --telegram-token=YOUR_BOT_TOKEN \
  --openai-key=YOUR_OPENAI_KEY
```

**Или интерактивный режим:**
```bash
sudo bash deploy.sh --interactive
```

---

## Важные замечания

1. **Не трогать существующие контейнеры** — скрипт использует уникальные имена с префиксом `assistant-`

2. **Не занимать используемые порты** — скрипт автоматически ищет свободные

3. **Backup перед деплоем** — скрипт должен напомнить о бэкапе если обнаружит существующую установку

4. **Rollback** — при ошибке скрипт должен откатить изменения в Nginx и остановить контейнеры

5. **Логирование** — все действия логируются в `/var/log/telegram-ai-assistant-deploy.log`
