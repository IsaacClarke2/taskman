# Development Instructions for Claude Code

> Этот документ — инструкция для Claude Code по разработке Telegram AI Business Assistant.
> Читай последовательно и выполняй по порядку.

---

## Обзор проекта

**Что делаем:** Telegram-бот, который принимает текст/голосовые/пересланные сообщения, распознаёт их через AI и создаёт события в календарях или заметки в Notion.

**Ключевые файлы для контекста:**
- `CLAUDE.md` — твой главный конфиг-файл
- `docs/PROJECT_SPEC.md` — полные требования к продукту и архитектуре
- `docs/ARCHITECTURE.md` — схема системы и data flows
- `docs/PROJECT_STATUS.md` — текущий прогресс (обновляй после каждой крупной задачи)

**Перед началом работы:** Всегда читай эти файлы, чтобы понимать контекст.

---

## Порядок разработки

Выполняй задачи строго в указанном порядке. Каждый блок должен быть завершён и протестирован перед переходом к следующему.

### БЛОК 1: Database & Core API

#### 1.1 Database Models (SQLAlchemy)

Создай модели в `db/models.py`:

```
users
├── id (UUID, PK)
├── telegram_id (BIGINT, unique, not null)
├── telegram_username (VARCHAR)
├── email (VARCHAR)
├── timezone (VARCHAR, default 'Europe/Moscow')
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

organizations
├── id (UUID, PK)
├── name (VARCHAR)
├── plan (VARCHAR, default 'free')
└── created_at (TIMESTAMP)

org_memberships
├── user_id (FK → users)
├── org_id (FK → organizations)
├── role (VARCHAR, default 'member')
├── joined_at (TIMESTAMP)
└── PK (user_id, org_id)

integrations
├── id (UUID, PK)
├── user_id (FK → users)
├── provider (VARCHAR) — google_calendar, outlook, apple_calendar, notion, apple_notes
├── credentials (JSONB) — encrypted tokens
├── settings (JSONB)
├── is_active (BOOLEAN, default true)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

calendars
├── id (UUID, PK)
├── integration_id (FK → integrations)
├── external_id (VARCHAR) — ID календаря во внешней системе
├── name (VARCHAR)
├── color (VARCHAR)
├── is_primary (BOOLEAN, default false)
├── is_enabled (BOOLEAN, default true)
└── created_at (TIMESTAMP)

events_log
├── id (UUID, PK)
├── user_id (FK → users)
├── calendar_id (FK → calendars, nullable)
├── external_event_id (VARCHAR)
├── original_message (TEXT)
├── parsed_data (JSONB)
├── status (VARCHAR) — created, failed, cancelled
└── created_at (TIMESTAMP)

notion_databases
├── id (UUID, PK)
├── integration_id (FK → integrations)
├── external_id (VARCHAR)
├── name (VARCHAR)
├── is_default (BOOLEAN, default false)
└── created_at (TIMESTAMP)
```

**Библиотека:** SQLAlchemy 2.0+ с asyncpg
**Документация:** https://docs.sqlalchemy.org/en/20/orm/quickstart.html

#### 1.2 Alembic Migrations

Настрой Alembic для async:
- `alembic init db/migrations`
- Настрой `alembic.ini` и `env.py` для async PostgreSQL
- Создай initial migration

**Документация:** https://alembic.sqlalchemy.org/en/latest/

#### 1.3 FastAPI Application

Создай базовую структуру в `api/`:

```
api/
├── main.py              # FastAPI app, CORS, routes
├── config.py            # Pydantic Settings
├── dependencies.py      # Dependency injection (db session, current user)
├── routers/
│   ├── auth.py          # Telegram auth verification
│   ├── integrations.py  # CRUD for integrations
│   ├── calendars.py     # Calendar operations
│   └── webhooks.py      # Telegram webhook, OAuth callbacks
├── services/
│   ├── parser.py        # Whisper + GPT
│   ├── router.py        # Event vs Note routing
│   └── slot_finder.py   # Free/busy logic
├── connectors/
│   ├── base.py          # Abstract base connector
│   ├── google_calendar.py
│   ├── outlook.py
│   ├── apple_calendar.py
│   ├── notion.py
│   └── apple_notes.py
└── models/
    ├── requests.py      # Pydantic request models
    └── responses.py     # Pydantic response models
```

**Библиотека:** FastAPI 0.109+
**Документация:** https://fastapi.tiangolo.com/

---

### БЛОК 2: Telegram Bot

#### 2.1 Bot Structure

Создай бота в `bot/`:

```
bot/
├── main.py              # Entry point, polling/webhook setup
├── config.py            # Bot settings
├── handlers/
│   ├── start.py         # /start command
│   ├── messages.py      # Text, voice, forwarded handlers
│   └── callbacks.py     # Inline button callbacks
├── keyboards/
│   ├── inline.py        # Inline keyboards for confirmations
│   └── builders.py      # Keyboard builder helpers
├── middlewares/
│   ├── auth.py          # Check user exists, create if not
│   └── throttling.py    # Rate limiting
├── states/
│   └── event.py         # FSM states for event creation
└── utils/
    ├── api_client.py    # HTTP client to Core API
    └── formatters.py    # Message formatting helpers
```

**Библиотека:** aiogram 3.x
**Документация:** https://docs.aiogram.dev/en/latest/

#### 2.2 Message Handlers

Реализуй три типа сообщений:

**Text handler:**
```python
@router.message(F.text)
async def handle_text(message: Message):
    # 1. Отправить текст в Parser Service
    # 2. Получить parsed result
    # 3. Показать inline keyboard с подтверждением
```

**Voice handler:**
```python
@router.message(F.voice)
async def handle_voice(message: Message):
    # 1. Скачать .oga файл через bot.download()
    # 2. Отправить в Whisper API для транскрипции
    # 3. Отправить текст в Parser Service
    # 4. Показать inline keyboard
```

**Forwarded handler:**
```python
@router.message(F.forward_date)
async def handle_forwarded(message: Message):
    # 1. Извлечь текст + информацию об отправителе
    # 2. Отправить в Parser Service с контекстом
    # 3. Показать inline keyboard
```

#### 2.3 Inline Keyboards

Формат подтверждения события:
```
📅 {title}
🕐 {date}, {time} – {end_time}
📍 {location или "Не указано"}
📅 Календарь: {calendar_name}

[✓ Создать] [✎ Изменить] [📅 Другой календарь] [✗ Отмена]
```

Callback data format: `action:event_id:extra`
- `confirm:uuid` — создать событие
- `edit:uuid` — редактировать (запустить FSM)
- `calendar:uuid` — выбрать другой календарь
- `cancel:uuid` — отменить

---

### БЛОК 3: AI Services (Parser)

#### 3.1 Whisper Integration

Файл: `api/services/parser.py`

```python
async def transcribe_voice(audio_bytes: bytes) -> str:
    """
    Отправляет аудио в OpenAI Whisper API.
    Telegram присылает .oga (Opus), Whisper принимает напрямую.
    """
```

**API:** OpenAI Whisper
**Документация:** https://platform.openai.com/docs/guides/speech-to-text
**Модель:** `whisper-1`

#### 3.2 GPT Parsing

Файл: `api/services/parser.py`

```python
async def parse_message(
    text: str,
    user_timezone: str,
    forwarded_from: str | None = None
) -> ParsedContent:
    """
    Отправляет текст в GPT для извлечения структуры.
    Возвращает ParsedContent с типом (event/note/unclear).
    """
```

**Промпт для GPT** (вставь в код):

```
You are a message parser for a calendar assistant. Extract event or note information from user messages.

Current datetime: {current_datetime}
User timezone: {user_timezone}
{f"Message forwarded from: {forwarded_from}" if forwarded_from else ""}

Analyze the message and return ONLY valid JSON:
{
  "content_type": "event" | "note" | "unclear",
  "confidence": 0.0-1.0,
  
  "title": "event/note title",
  "start_datetime": "ISO 8601 with timezone or null",
  "end_datetime": "ISO 8601 with timezone or null",
  "duration_minutes": 60,
  "location": "location or null",
  "participants": ["names or emails"],
  
  "note_content": "for notes only",
  
  "clarification_needed": "what's missing, if unclear"
}

Rules:
- If no time specified, set start_datetime to null
- Default duration: 60 minutes
- "завтра" = tomorrow, "послезавтра" = day after tomorrow
- "после обеда" = 14:00, "утром" = 10:00, "вечером" = 19:00
- "на следующей неделе" = next Monday
- Keywords "идея", "мысль", "заметка", "запомни" → content_type = "note"
- Keywords with date/time + action/person → content_type = "event"
- Return ONLY JSON, no markdown, no explanation
```

**API:** OpenAI Responses API (новый) или Chat Completions
**Документация:** https://platform.openai.com/docs/guides/text-generation
**Модель:** `gpt-5-mini` (дешёвый и быстрый, $0.25/1M input, $2/1M output)
**Альтернатива:** `gpt-5-nano` ещё дешевле ($0.05/1M input) для простых задач

---

### БЛОК 4: Calendar Connectors

#### 4.1 Base Connector Interface

Файл: `api/connectors/base.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
from pydantic import BaseModel

class Event(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None
    calendar_id: str

class TimeSlot(BaseModel):
    start: datetime
    end: datetime

class Calendar(BaseModel):
    id: str
    name: str
    color: str | None
    is_primary: bool

class EventCreate(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None

class BaseConnector(ABC):
    def __init__(self, credentials: dict):
        self.credentials = credentials
    
    @abstractmethod
    async def test_connection(self) -> bool:
        pass
    
    @abstractmethod
    async def refresh_token(self) -> dict:
        pass

class CalendarConnector(BaseConnector):
    @abstractmethod
    async def list_calendars(self) -> List[Calendar]:
        pass
    
    @abstractmethod
    async def create_event(self, calendar_id: str, event: EventCreate) -> Event:
        pass
    
    @abstractmethod
    async def list_events(self, calendar_id: str, start: datetime, end: datetime) -> List[Event]:
        pass
    
    @abstractmethod
    async def get_free_slots(self, calendar_id: str, start: datetime, end: datetime) -> List[TimeSlot]:
        pass
    
    @abstractmethod
    async def check_conflicts(self, calendar_id: str, start: datetime, end: datetime) -> List[Event]:
        pass
```

#### 4.2 Google Calendar Connector

Файл: `api/connectors/google_calendar.py`

**OAuth Flow:**
1. Redirect user to Google OAuth URL
2. User authorizes
3. Google redirects to callback with `code`
4. Exchange code for tokens
5. Store encrypted tokens in DB

**Scopes needed:**
- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/calendar.readonly`

**Библиотека:** `google-api-python-client` + `google-auth-oauthlib`
**Документация:** 
- OAuth: https://developers.google.com/identity/protocols/oauth2/web-server
- Calendar API: https://developers.google.com/calendar/api/v3/reference

**Важно:** Получи актуальные версии библиотек из PyPI:
- https://pypi.org/project/google-api-python-client/
- https://pypi.org/project/google-auth-oauthlib/

#### 4.3 Outlook Connector

Файл: `api/connectors/outlook.py`

**OAuth Flow:** Microsoft Identity Platform (MSAL)

**Scopes needed:**
- `Calendars.ReadWrite`
- `User.Read`

**Библиотека:** `msal` + `httpx` для Microsoft Graph API
**Документация:**
- MSAL Python: https://github.com/AzureAD/microsoft-authentication-library-for-python
- Graph Calendar API: https://learn.microsoft.com/en-us/graph/api/resources/calendar

**Важно:** Получи актуальную версию MSAL из PyPI:
- https://pypi.org/project/msal/

#### 4.4 Apple Calendar Connector (CalDAV)

Файл: `api/connectors/apple_calendar.py`

**Auth:** App-specific password (не OAuth)
- User создаёт password на appleid.apple.com
- Вводит email + app-specific password в нашей панели
- Мы подключаемся к `caldav.icloud.com`

**Библиотека:** `caldav`
**Документация:** https://caldav.readthedocs.io/

**Важно:** Получи актуальную версию из PyPI:
- https://pypi.org/project/caldav/

**Пример подключения:**
```python
import caldav

client = caldav.DAVClient(
    url="https://caldav.icloud.com",
    username="user@icloud.com",
    password="app-specific-password"
)
principal = client.principal()
calendars = principal.calendars()
```

---

### БЛОК 5: Notes Connectors

#### 5.1 Notion Connector

Файл: `api/connectors/notion.py`

**OAuth Flow:** Notion OAuth 2.0

**Capabilities:**
- Create pages in databases
- List databases user shared with integration

**Библиотека:** `httpx` (Notion API простой, SDK не нужен)
**Документация:** https://developers.notion.com/reference/intro

**API Base URL:** `https://api.notion.com/v1`
**Headers:**
```
Authorization: Bearer {access_token}
Notion-Version: 2022-06-28
```

#### 5.2 Apple Notes Connector (Shortcut Bridge)

Файл: `api/connectors/apple_notes.py`

**Механизм:** iOS Shortcut + Webhook

**Как работает:**
1. Пользователь устанавливает наш Shortcut на iPhone
2. Shortcut содержит automation: "When webhook received → Create Note"
3. Мы отправляем POST на webhook URL
4. Shortcut создаёт заметку в Apple Notes

**Реализация:**
1. Создай файл Shortcut (.shortcut) — см. отдельную инструкцию
2. В connector просто отправляй HTTP POST на URL, который пользователь указал после установки Shortcut

**Альтернатива:** Использовать Push Notification + Shortcut Automation

---

### БЛОК 6: Web Panel (Next.js)

#### 6.1 Structure

```
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                    # Landing / Login
│   ├── dashboard/
│   │   └── page.tsx                # Main dashboard
│   ├── integrations/
│   │   ├── page.tsx                # List integrations
│   │   ├── google/
│   │   │   └── callback/page.tsx   # OAuth callback
│   │   ├── outlook/
│   │   │   └── callback/page.tsx
│   │   ├── notion/
│   │   │   └── callback/page.tsx
│   │   ├── apple-calendar/
│   │   │   └── page.tsx            # Manual setup form
│   │   └── apple-notes/
│   │       └── page.tsx            # Shortcut instructions
│   └── settings/
│       └── page.tsx
├── components/
│   ├── TelegramLoginButton.tsx
│   ├── IntegrationCard.tsx
│   ├── CalendarSelector.tsx
│   └── InstructionVideo.tsx
└── lib/
    ├── api.ts                      # API client
    └── auth.ts                     # Auth helpers
```

#### 6.2 Telegram Login Widget

**Документация:** https://core.telegram.org/widgets/login

Пример компонента:
```tsx
// components/TelegramLoginButton.tsx
export function TelegramLoginButton({ botUsername, onAuth }) {
  useEffect(() => {
    window.TelegramLoginWidget = {
      dataOnauth: (user) => onAuth(user)
    };
    
    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute('data-telegram-login', botUsername);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-onauth', 'TelegramLoginWidget.dataOnauth(user)');
    script.setAttribute('data-request-access', 'write');
    document.getElementById('telegram-login').appendChild(script);
  }, []);
  
  return <div id="telegram-login" />;
}
```

**Верификация на бэкенде:**
```python
import hashlib
import hmac

def verify_telegram_auth(data: dict, bot_token: str) -> bool:
    check_hash = data.pop('hash')
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), 'sha256').hexdigest()
    return computed == check_hash
```

#### 6.3 OAuth Callbacks

Каждый callback делает:
1. Получает `code` из query params
2. Отправляет на backend: `POST /api/integrations/{provider}/callback`
3. Backend обменивает code на tokens
4. Редирект на `/integrations` с success message

---

### БЛОК 7: Background Workers

#### 7.1 arq Setup

Файл: `workers/main.py`

```python
from arq import create_pool
from arq.connections import RedisSettings

async def transcribe_voice(ctx, audio_bytes: bytes, user_id: str, message_id: int):
    """Транскрибирует голосовое через Whisper"""
    pass

async def create_calendar_event(ctx, user_id: str, integration_id: str, event_data: dict):
    """Создаёт событие в календаре"""
    pass

async def refresh_tokens(ctx):
    """Обновляет OAuth токены, которые скоро истекут"""
    pass

class WorkerSettings:
    functions = [transcribe_voice, create_calendar_event]
    cron_jobs = [
        cron(refresh_tokens, hour=3, minute=0)  # Every day at 3 AM
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
```

**Библиотека:** arq
**Документация:** https://arq-docs.helpmanual.io/

---

### БЛОК 8: Security

#### 8.1 Token Encryption

Файл: `api/utils/crypto.py`

```python
from cryptography.fernet import Fernet

def encrypt_credentials(data: dict, key: bytes) -> str:
    """Шифрует credentials перед сохранением в БД"""
    pass

def decrypt_credentials(encrypted: str, key: bytes) -> dict:
    """Расшифровывает credentials из БД"""
    pass
```

**Библиотека:** cryptography
**Документация:** https://cryptography.io/en/latest/fernet/

#### 8.2 Environment Variables

Все секреты только через environment variables:
- `ENCRYPTION_KEY` — для шифрования токенов
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`
- `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`

---

## Чеклист перед каждым коммитом

1. [ ] Код работает локально
2. [ ] Нет hardcoded secrets
3. [ ] Type hints везде
4. [ ] Обработка ошибок для внешних API
5. [ ] Логирование важных операций
6. [ ] Обновлён `docs/PROJECT_STATUS.md`

---

## Команды для разработки

```bash
# Запуск всех сервисов
docker-compose up -d

# Логи
docker-compose logs -f bot
docker-compose logs -f api

# Миграции
docker-compose exec api alembic upgrade head
docker-compose exec api alembic revision --autogenerate -m "description"

# Тесты
docker-compose exec api pytest tests/ -v

# Перезапуск после изменений
docker-compose restart bot api
```

---

## Где брать актуальные версии библиотек

Перед установкой проверь последние версии:

| Библиотека | PyPI страница |
|------------|---------------|
| aiogram | https://pypi.org/project/aiogram/ |
| fastapi | https://pypi.org/project/fastapi/ |
| sqlalchemy | https://pypi.org/project/sqlalchemy/ |
| openai | https://pypi.org/project/openai/ |
| google-api-python-client | https://pypi.org/project/google-api-python-client/ |
| msal | https://pypi.org/project/msal/ |
| caldav | https://pypi.org/project/caldav/ |
| arq | https://pypi.org/project/arq/ |
| cryptography | https://pypi.org/project/cryptography/ |

**Next.js:**
- https://nextjs.org/docs — всегда актуальная документация
- Используй `npx create-next-app@latest` для последней версии

---

## Приоритет при проблемах

Если что-то не работает:

1. **Проверь логи** — `docker-compose logs -f {service}`
2. **Проверь документацию библиотеки** — версии API могут меняться
3. **Проверь .env** — все переменные заданы?
4. **Проверь сеть** — контейнеры видят друг друга?

При ошибках внешних API (Google, OpenAI, etc):
1. Проверь что токены/ключи валидны
2. Проверь rate limits
3. Проверь формат запроса в документации API
