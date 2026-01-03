# Project Spec: Telegram AI Business Assistant

## Project Goal

**Type:** MVP for idea validation with real users  
**Target:** 20-30 beta testers (entrepreneurs, top managers)  
**Success Criteria:** Users create 10+ events through the bot within first week

---

## Part 1: Product Requirements

### 1.1 Target User

**Primary Persona:** Предприниматель / топ-менеджер
- Живёт в Telegram (основной мессенджер)
- Использует несколько календарей (личный, рабочий, проектные)
- Часто надиктовывает голосовые сообщения
- Пересылает себе сообщения как напоминания
- Не хочет учиться новым инструментам

### 1.2 Problems We Solve

1. **Friction при создании событий** — переключение между приложениями, ручной ввод
2. **Разрозненные календари** — сложно управлять несколькими календарями
3. **Потеря контекста** — переслал сообщение себе, забыл что с ним делать
4. **Голосовые = мёртвый контент** — надиктовал, но не переложил в систему

### 1.3 Core User Flows

#### Flow 1: Создание события из текста
```
User: [пишет в бот] "Завтра в 15:00 созвон с Петровым по контракту"

Bot: 📅 Созвон с Петровым
     🕐 Завтра, 15:00 – 16:00
     📝 По контракту
     📍 Календарь: Рабочий (основной)
     
     [✓ Создать] [✎ Изменить] [📅 Другой календарь] [✗ Отмена]

User: [нажимает "Создать"]

Bot: ✓ Событие создано в календаре "Рабочий"
     [Открыть в Google Calendar]
```

#### Flow 2: Создание события из голосового
```
User: [отправляет голосовое] "Надо не забыть в пятницу встретиться 
       с инвестором, часов в одиннадцать утра в кофейне на Патриках"

Bot: 📅 Встреча с инвестором
     🕐 Пятница, 11:00 – 12:00
     📍 Кофейня на Патриарших
     📅 Календарь: Рабочий (основной)
     
     [✓ Создать] [✎ Изменить] [📅 Другой календарь] [✗ Отмена]
```

#### Flow 3: Создание события из пересланного сообщения
```
User: [пересылает сообщение из другого чата]
      "Давай созвонимся во вторник после обеда, часа в 2?"

Bot: 📅 Созвон (уточните название)
     🕐 Вторник, 14:00 – 15:00
     👤 Участник: [имя отправителя из пересланного]
     
     [✓ Создать] [✎ Изменить] [✗ Отмена]
```

#### Flow 4: Создание заметки (v0.2+)
```
User: [пишет] "Идея: сделать геймификацию в мобильном банке 
       через достижения за регулярные платежи"

Bot: Это похоже на заметку. Куда сохранить?
     
     [📓 Notion] [📅 Напомнить позже] [✗ Отмена]

User: [нажимает "Notion"]

Bot: ✓ Сохранено в Notion → Inbox
     [Открыть заметку]
```

#### Flow 5: Конфликт времени
```
User: "Встреча с банком завтра в 10"

Bot: ⚠️ Конфликт: у тебя уже есть "Планёрка с командой" в 10:00
     
     Варианты:
     [🕐 Поставить на 11:00] [🔄 Заменить планёрку] [➕ Создать всё равно]
```

#### Flow 6: Умные слоты (если время не указано)
```
User: "Нужно созвониться с юристом на этой неделе"

Bot: 📅 Созвон с юристом
     
     Свободные слоты на этой неделе:
     [Вт 14:00] [Ср 11:00] [Чт 16:00]
     
     [✎ Указать время вручную]
```

### 1.4 Web Panel Flows

#### Flow: Подключение Google Calendar
```
1. User открывает webapp через кнопку в боте
2. Видит список интеграций: Google Calendar, Outlook, Notion...
3. Нажимает "Подключить" напротив Google Calendar
4. Редирект на Google OAuth
5. Даёт разрешения
6. Редирект обратно в webapp
7. Видит список своих календарей
8. Выбирает основной календарь (в который по умолчанию)
9. Опционально: включает/выключает отдельные календари
```

#### Flow: Подключение Apple Calendar
```
1. User нажимает "Подключить" напротив Apple Calendar
2. Видит инструкцию: "Создайте app-specific password"
3. Ссылка на appleid.apple.com
4. Поле для ввода email и app-specific password
5. Проверка подключения
6. Список календарей, выбор основного
```

#### Flow: Подключение Apple Notes (через Shortcut)
```
1. User нажимает "Подключить" напротив Apple Notes
2. Видит: "Apple Notes требует установки Shortcut на iPhone"
3. Кнопка "Скачать Shortcut" + видео-инструкция (2 мин)
4. После установки: кнопка "Проверить подключение"
5. Бот отправляет тестовую заметку
6. User подтверждает, что заметка появилась
```

### 1.5 Release Scope (v1.0)

**Single release with all features:**

#### Core Bot
- [ ] Telegram бот принимает текст, голосовые, пересланные сообщения
- [ ] OpenAI Whisper для распознавания голосовых
- [ ] GPT для парсинга (событие vs заметка)
- [ ] Inline keyboard для подтверждения
- [ ] Конфликт-детект
- [ ] Умные слоты (free/busy)

#### Календари
- [ ] Google Calendar (OAuth)
- [ ] Outlook/Microsoft 365 (OAuth)
- [ ] Apple Calendar (CalDAV + app-specific password)
- [ ] Множественные календари на аккаунт
- [ ] Выбор основного календаря

#### Заметки
- [ ] Notion (OAuth)
- [ ] Apple Notes (iOS Shortcut + инструкция)

#### Веб-панель
- [ ] Авторизация через Telegram Widget
- [ ] Подключение/отключение интеграций
- [ ] Настройка основного календаря
- [ ] Инструкции для Apple (CalDAV, Shortcut)

#### Командный режим (архитектурно заложен)
- [ ] Модель данных для организаций
- [ ] Права доступа к календарям
- [ ] Поиск слотов для команды
- [ ] UI пока не делаем, но API готов

---

## Part 2: Engineering Requirements

### 2.1 Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Bot Framework | Python + aiogram 3.x | Async, modern, well-maintained |
| Web Backend | Python + FastAPI | Async, fast, easy to write |
| Web Frontend | React + Next.js | SSR for OAuth flows, good DX |
| Database | PostgreSQL | Reliable, good for relational data |
| Cache/Queue | Redis + arq | Lightweight, good for background jobs |
| AI - Speech | OpenAI Whisper API | Best quality for voice recognition |
| AI - Parsing | OpenAI GPT-5-mini | Cheap ($0.25/1M input), fast, smart enough for parsing |
| Hosting | VPS (Netherlands) + domain corben.pro | Already available, SSL required for Telegram Widget |
| Containers | Docker + docker-compose | Simple for MVP, auto port selection |

### 2.2 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                               │
│                         (Traefik)                                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Telegram   │      │   Web App    │      │   Webhook    │
│   Gateway    │      │   (Next.js)  │      │   Receiver   │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             ▼
                    ┌─────────────────┐
                    │   Core Service  │
                    │    (FastAPI)    │
                    └────────┬────────┘
                             │
        ┌───────────┬────────┼────────┬───────────┐
        ▼           ▼        ▼        ▼           ▼
┌───────────┐ ┌─────────┐ ┌───────┐ ┌───────┐ ┌─────────┐
│  Parser   │ │ Router  │ │ Slot  │ │ Team  │ │  Sync   │
│  Module   │ │ Module  │ │Finder │ │Module │ │ Module  │
└───────────┘ └─────────┘ └───────┘ └───────┘ └─────────┘
                             │
        ┌───────────┬────────┼────────┬───────────┐
        ▼           ▼        ▼        ▼           ▼
┌───────────┐ ┌─────────┐ ┌───────┐ ┌───────┐ ┌─────────┐
│  Google   │ │Outlook  │ │ Apple │ │ Apple │ │ Notion  │
│ Calendar  │ │Calendar │ │  Cal  │ │ Notes │ │Connector│
│ Connector │ │Connector│ │Connec.│ │Connec.│ │         │
└───────────┘ └─────────┘ └───────┘ └───────┘ └─────────┘
```

### 2.3 Database Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(255),
    email VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Organizations (for team mode, v1.0)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Organization memberships
CREATE TABLE org_memberships (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, org_id)
);

-- Integrations
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL, -- google_calendar, outlook, apple_calendar, notion, apple_notes
    credentials JSONB NOT NULL, -- encrypted tokens
    settings JSONB DEFAULT '{}', -- provider-specific settings
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- Calendars (for multi-calendar support)
CREATE TABLE calendars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID REFERENCES integrations(id) ON DELETE CASCADE,
    external_id VARCHAR(255) NOT NULL, -- calendar ID in external system
    name VARCHAR(255) NOT NULL,
    color VARCHAR(20),
    is_primary BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Events log (for analytics and debugging)
CREATE TABLE events_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    calendar_id UUID REFERENCES calendars(id) ON DELETE SET NULL,
    external_event_id VARCHAR(255),
    original_message TEXT,
    parsed_data JSONB,
    status VARCHAR(50), -- created, failed, cancelled
    created_at TIMESTAMP DEFAULT NOW()
);

-- Notion databases (for routing notes)
CREATE TABLE notion_databases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID REFERENCES integrations(id) ON DELETE CASCADE,
    external_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.4 API Contracts

#### Parser Service Input/Output
```python
# Input
class ParseRequest(BaseModel):
    message_type: Literal["text", "voice", "forwarded"]
    content: str  # text or transcribed voice
    forwarded_from: Optional[str] = None
    user_timezone: str = "Europe/Moscow"

# Output
class ParsedContent(BaseModel):
    content_type: Literal["event", "note", "reminder", "unclear"]
    confidence: float  # 0.0 - 1.0
    
    # For events
    title: Optional[str]
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    duration_minutes: Optional[int] = 60
    location: Optional[str]
    participants: Optional[List[str]]
    
    # For notes
    note_title: Optional[str]
    note_content: Optional[str]
    
    # For unclear
    clarification_needed: Optional[str]
```

#### Calendar Connector Interface
```python
from abc import ABC, abstractmethod

class CalendarConnector(ABC):
    @abstractmethod
    async def create_event(self, event: EventCreate) -> EventResult:
        pass
    
    @abstractmethod
    async def list_events(self, start: datetime, end: datetime) -> List[Event]:
        pass
    
    @abstractmethod
    async def get_free_slots(self, start: datetime, end: datetime) -> List[TimeSlot]:
        pass
    
    @abstractmethod
    async def list_calendars(self) -> List[Calendar]:
        pass
    
    @abstractmethod
    async def check_conflicts(self, start: datetime, end: datetime) -> List[Event]:
        pass
```

### 2.5 GPT Prompt for Parsing

```
You are a message parser for a calendar assistant. Extract event or note information from user messages.

Current date and time: {current_datetime}
User timezone: {user_timezone}

Analyze the message and return JSON:
{
  "content_type": "event" | "note" | "reminder" | "unclear",
  "confidence": 0.0-1.0,
  
  // For events:
  "title": "event title",
  "start_datetime": "ISO 8601 datetime",
  "end_datetime": "ISO 8601 datetime or null",
  "duration_minutes": 60,
  "location": "location or null",
  "participants": ["name or email"],
  
  // For notes:
  "note_title": "title",
  "note_content": "content",
  
  // If unclear:
  "clarification_needed": "what information is missing"
}

Rules:
- If no time specified, set start_datetime to null
- If no duration specified, default to 60 minutes
- "Завтра" = tomorrow, "послезавтра" = day after tomorrow
- "После обеда" = 14:00, "утром" = 10:00, "вечером" = 19:00
- If message contains "идея", "мысль", "заметка" → content_type = "note"
- If message contains date/time + action/meeting → content_type = "event"
- Respond ONLY with valid JSON, no additional text
```

### 2.6 Security Requirements

- All credentials encrypted at rest (AES-256)
- OAuth tokens stored with encryption
- App-specific passwords for Apple hashed before storage
- HTTPS everywhere
- Rate limiting on bot and API
- Telegram webhook verification
- No sensitive data in logs

### 2.7 Constraints and Policies

- Never store raw OAuth refresh tokens in logs
- Always use environment variables for secrets
- Never push to main directly (use PRs)
- All database migrations must be reversible
- Keep Telegram message handling under 3 seconds
- Background jobs for API calls to external services

---

## Part 3: Development Order

### Week 1: Foundation + Core Bot
1. Project setup: repo, docker-compose, CI/CD
2. Database schema and migrations
3. FastAPI structure + basic endpoints
4. Telegram bot: text messages, inline keyboards
5. Whisper integration for voice
6. GPT parsing integration

### Week 2: Google Calendar + Notion
1. Web app: Telegram auth widget
2. Google Calendar OAuth flow
3. Google Calendar connector (create, list, free/busy)
4. Multiple calendars + primary selection
5. Notion OAuth flow
6. Notion connector (create pages)
7. Router: event vs note detection

### Week 3: Outlook + Apple Calendar
1. Microsoft OAuth flow (MSAL)
2. Outlook connector (Microsoft Graph API)
3. Apple Calendar setup UI (app-specific password instructions)
4. Apple Calendar connector (CalDAV)
5. Conflict detection
6. Smart slot suggestions

### Week 4: Apple Notes + Polish
1. Apple Notes Shortcut creation
2. Video/text instructions for Shortcut setup
3. Webhook bridge for Shortcut
4. Forwarded messages handling
5. Error handling + edge cases
6. Testing with beta users

### Week 5: Team Mode Foundation (API only)
1. Organizations model
2. Permissions system
3. Multi-user slot finder
4. Invite flow (API)
5. Documentation + deployment
