# Architecture: Telegram AI Business Assistant

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                               │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│  Telegram API   │   OpenAI API    │  Google APIs    │   Microsoft Graph     │
│                 │ (Whisper + GPT) │ (Calendar)      │   (Outlook)           │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (Traefik)                           │
│                         - SSL termination                                    │
│                         - Rate limiting                                      │
│                         - Request routing                                    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│  TELEGRAM BOT   │        │   WEB APP       │        │  WEBHOOK        │
│    (aiogram)    │        │   (Next.js)     │        │  RECEIVER       │
├─────────────────┤        ├─────────────────┤        ├─────────────────┤
│ - Message recv  │        │ - OAuth flows   │        │ - Calendar sync │
│ - Voice files   │        │ - Settings UI   │        │ - Token refresh │
│ - Inline KB     │        │ - Dashboard     │        │                 │
└────────┬────────┘        └────────┬────────┘        └────────┬────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE SERVICE (FastAPI)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   PARSER    │  │   ROUTER    │  │ SLOT FINDER │  │    TEAM     │        │
│  │   MODULE    │  │   MODULE    │  │   MODULE    │  │   MODULE    │        │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤        │
│  │ - Whisper   │  │ - Type det. │  │ - Free/busy │  │ - Orgs      │        │
│  │ - GPT parse │  │ - Calendar  │  │ - Conflicts │  │ - Perms     │        │
│  │ - Normalize │  │   selection │  │ - Suggest   │  │ - Invites   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│     GOOGLE      │        │     OUTLOOK     │        │     APPLE       │
│    CALENDAR     │        │    CALENDAR     │        │   CALENDAR      │
│   CONNECTOR     │        │   CONNECTOR     │        │   CONNECTOR     │
├─────────────────┤        ├─────────────────┤        ├─────────────────┤
│ - OAuth 2.0     │        │ - MS Graph API  │        │ - CalDAV        │
│ - REST API      │        │ - OAuth 2.0     │        │ - App password  │
└─────────────────┘        └─────────────────┘        └─────────────────┘

┌─────────────────┐        ┌─────────────────┐
│     NOTION      │        │   APPLE NOTES   │
│   CONNECTOR     │        │   CONNECTOR     │
├─────────────────┤        ├─────────────────┤
│ - REST API      │        │ - iOS Shortcut  │
│ - OAuth 2.0     │        │ - Webhook bridge│
└─────────────────┘        └─────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
├──────────────────────────────────┬──────────────────────────────────────────┤
│         PostgreSQL               │              Redis                        │
├──────────────────────────────────┼──────────────────────────────────────────┤
│ - Users                          │ - Session cache                          │
│ - Organizations                  │ - Rate limiting                          │
│ - Integrations                   │ - Job queues (arq)                       │
│ - Calendars                      │ - OAuth state                            │
│ - Events log                     │                                          │
└──────────────────────────────────┴──────────────────────────────────────────┘
```

## Component Details

### 1. Telegram Bot (aiogram)

**Responsibilities:**
- Receive messages (text, voice, forwarded)
- Download voice files
- Send inline keyboard responses
- Handle button callbacks

**Key Handlers:**
```python
@router.message(F.text)
async def handle_text(message: Message)

@router.message(F.voice)
async def handle_voice(message: Message)

@router.message(F.forward)
async def handle_forwarded(message: Message)

@router.callback_query()
async def handle_callback(callback: CallbackQuery)
```

**State Management:**
- Uses Redis for conversation state
- States: `idle`, `awaiting_confirmation`, `editing_event`, `selecting_calendar`

### 2. Core Service (FastAPI)

**Modules:**

#### Parser Module
- Converts voice to text (Whisper API)
- Extracts structured data from text (GPT)
- Normalizes dates/times to user timezone

#### Router Module
- Determines content type (event/note/reminder)
- Selects target integration based on user settings
- Handles routing rules

#### Slot Finder Module
- Queries free/busy from calendars
- Finds intersection of free slots (for team mode)
- Ranks slots by preference (working hours, etc.)

#### Team Module (v1.0)
- Organization management
- Permission system
- Calendar sharing

### 3. Connectors

All connectors implement `BaseConnector`:

```python
class BaseConnector(ABC):
    user_id: UUID
    integration_id: UUID
    
    async def authenticate(self, credentials: dict) -> bool
    async def refresh_token(self) -> str
    async def test_connection(self) -> bool
```

#### Google Calendar Connector
- OAuth 2.0 flow
- Scopes: `calendar.events`, `calendar.readonly`
- Supports multiple calendars per account

#### Outlook Connector
- Microsoft Graph API
- OAuth 2.0 with MSAL
- Scopes: `Calendars.ReadWrite`

#### Apple Calendar Connector
- CalDAV protocol
- App-specific password authentication
- iCloud CalDAV endpoint: `caldav.icloud.com`

#### Notion Connector
- REST API v1
- OAuth 2.0
- Creates pages in specified database

#### Apple Notes Connector
- No direct API — uses iOS Shortcut bridge
- Webhook triggers Shortcut on user's device
- Requires user setup (Shortcut installation)

### 4. Web App (Next.js)

**Pages:**

| Route | Purpose |
|-------|---------|
| `/` | Landing / login via Telegram widget |
| `/dashboard` | Overview of connected integrations |
| `/integrations` | Connect/disconnect services |
| `/integrations/google/callback` | OAuth callback |
| `/integrations/outlook/callback` | OAuth callback |
| `/settings` | User preferences, timezone |
| `/team` | Organization management (v1.0) |

**Auth Flow:**
1. User clicks "Login with Telegram" widget
2. Telegram sends auth data to our backend
3. Backend verifies signature, creates session
4. JWT stored in httpOnly cookie

### 5. Background Workers (arq)

**Jobs:**

| Job | Trigger | Purpose |
|-----|---------|---------|
| `transcribe_voice` | Voice message received | Call Whisper API |
| `create_calendar_event` | User confirms | Create event via connector |
| `refresh_tokens` | Scheduled (hourly) | Refresh OAuth tokens |
| `sync_calendars` | Scheduled (daily) | Update calendar cache |

### 6. Data Flow Examples

#### Creating Event from Voice Message

```
1. User sends voice message to bot
   │
   ▼
2. Bot downloads .oga file, enqueues transcription job
   │
   ▼
3. Worker calls Whisper API → returns text
   │
   ▼
4. Parser Module calls GPT → returns structured event
   │
   ▼
5. Slot Finder checks conflicts
   │
   ▼
6. Bot sends inline keyboard with event preview
   │
   ▼
7. User clicks "Create"
   │
   ▼
8. Worker calls Google Calendar API → event created
   │
   ▼
9. Bot sends confirmation with link
```

#### OAuth Flow (Google Calendar)

```
1. User clicks "Connect Google Calendar" in web app
   │
   ▼
2. Frontend redirects to Google OAuth
   │
   ▼
3. User authorizes, Google redirects to callback
   │
   ▼
4. Backend exchanges code for tokens
   │
   ▼
5. Tokens encrypted and stored in DB
   │
   ▼
6. Backend fetches calendar list
   │
   ▼
7. User selects primary calendar
   │
   ▼
8. Settings saved, integration active
```

## Security Architecture

### Token Storage
```
┌─────────────────────────────────────────┐
│           Integration Record             │
├─────────────────────────────────────────┤
│ provider: "google_calendar"             │
│ credentials: {                          │
│   access_token: <AES-256 encrypted>     │
│   refresh_token: <AES-256 encrypted>    │
│   expires_at: <timestamp>               │
│ }                                        │
└─────────────────────────────────────────┘
```

### Encryption
- Master key from environment variable
- Per-user encryption key derived from master + user_id
- AES-256-GCM for token encryption

### Telegram Verification
```python
def verify_telegram_auth(data: dict, bot_token: str) -> bool:
    check_hash = data.pop('hash')
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), 'sha256').hexdigest()
    return computed_hash == check_hash
```

## Scalability Considerations

### Current (MVP)
- Single VPS with docker-compose
- PostgreSQL and Redis on same machine
- Suitable for ~100 active users

### Future (v1.0+)
- Kubernetes deployment
- Managed PostgreSQL (e.g., Supabase, Neon)
- Managed Redis (e.g., Upstash)
- Horizontal scaling of workers
- CDN for web app

## Monitoring

### Metrics to Track
- Message processing latency
- Whisper API response time
- GPT parsing accuracy
- Calendar API success rate
- Error rates by type

### Logging
- Structured JSON logs
- Correlation IDs across services
- No PII in logs
