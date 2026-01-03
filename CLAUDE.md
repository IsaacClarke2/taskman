# CLAUDE.md — Telegram AI Business Assistant

## Project Overview

AI-powered Telegram bot that captures voice messages, text, and forwarded messages, parses them with GPT, and creates events in user's calendars or notes in Notion.

**Goal:** MVP for idea validation with 20-30 beta testers  
**Target Users:** Entrepreneurs and top managers who live in Telegram

## Quick Reference

### Key Files
- `docs/PROJECT_SPEC.md` — Full product and engineering requirements
- `docs/ARCHITECTURE.md` — System design and component interactions
- `docs/CHANGELOG.md` — History of changes
- `docs/PROJECT_STATUS.md` — Current progress and next steps

### Tech Stack
- **Bot:** Python 3.11+ / aiogram 3.x
- **Backend:** FastAPI
- **Frontend:** Next.js 14 (App Router)
- **Database:** PostgreSQL 15
- **Cache/Queue:** Redis + arq
- **AI:** OpenAI Whisper API + GPT-4o-mini
- **Containers:** Docker + docker-compose

### Project Structure
```
telegram-ai-assistant/
├── bot/                    # Telegram bot (aiogram)
│   ├── handlers/           # Message handlers
│   ├── keyboards/          # Inline keyboards
│   └── middlewares/        # Auth, rate limiting
├── api/                    # FastAPI backend
│   ├── routers/            # API routes
│   ├── services/           # Business logic
│   ├── connectors/         # External integrations
│   │   ├── google_calendar.py
│   │   ├── outlook.py
│   │   ├── apple_calendar.py
│   │   ├── notion.py
│   │   └── apple_notes.py
│   └── models/             # Pydantic models
├── web/                    # Next.js frontend
│   ├── app/                # App router pages
│   └── components/         # React components
├── db/                     # Database
│   ├── migrations/         # Alembic migrations
│   └── models.py           # SQLAlchemy models
├── workers/                # Background jobs (arq)
├── docs/                   # Documentation
├── tests/                  # Test suite
├── docker-compose.yml
└── .env.example
```

## Commands

### Development
```bash
# Start all services
docker-compose up -d

# Run bot locally
cd bot && python -m bot.main

# Run API locally
cd api && uvicorn api.main:app --reload

# Run web locally
cd web && npm run dev

# Run tests
pytest tests/ -v

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Git Workflow
```bash
# Feature branch
git checkout -b feature/calendar-integration

# Commit with conventional commits
git commit -m "feat(calendar): add Google Calendar OAuth flow"
git commit -m "fix(parser): handle timezone edge cases"

# Never push directly to main
git push origin feature/calendar-integration
# Then create PR
```

## Coding Guidelines

### Python Style
- Use type hints everywhere
- Async/await for I/O operations
- Pydantic for data validation
- Keep functions under 50 lines
- Docstrings for public functions

### Error Handling
```python
# Always use custom exceptions
class CalendarConnectionError(Exception):
    pass

# Always handle external API errors gracefully
try:
    result = await calendar.create_event(event)
except CalendarConnectionError as e:
    logger.error(f"Calendar error: {e}")
    await notify_user_of_error(user_id, "calendar_unavailable")
```

### Logging
```python
# Use structured logging
logger.info("Event created", extra={
    "user_id": user_id,
    "event_id": event.id,
    "calendar": calendar.name
})
```

### Secrets
- Never hardcode secrets
- Always use environment variables
- Use `.env` for local development
- Encrypt sensitive data at rest

## Connector Interface

All calendar/notes connectors must implement this interface:

```python
class BaseConnector(ABC):
    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        pass
    
    @abstractmethod
    async def refresh_token(self) -> str:
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        pass
```

Calendar connectors additionally implement:
```python
class CalendarConnector(BaseConnector):
    async def create_event(self, event: EventCreate) -> EventResult
    async def list_events(self, start: datetime, end: datetime) -> List[Event]
    async def get_free_slots(self, start: datetime, end: datetime) -> List[TimeSlot]
    async def list_calendars(self) -> List[Calendar]
    async def check_conflicts(self, start: datetime, end: datetime) -> List[Event]
```

## Current Focus

See `docs/PROJECT_STATUS.md` for current milestone and tasks.

## Constraints

1. **Response Time:** Telegram handler must respond within 3 seconds. Use background jobs for slow operations.

2. **Token Limits:** GPT-4o-mini context is 128k tokens. Keep parsing prompts under 2k tokens.

3. **Rate Limits:** 
   - OpenAI: 500 RPM for GPT-4o-mini
   - Google Calendar: 1M queries/day
   - Respect Telegram flood limits

4. **Security:**
   - All OAuth tokens encrypted with AES-256
   - App-specific passwords hashed with bcrypt
   - No sensitive data in logs
   - Telegram webhook signature verification

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires test credentials)
pytest tests/integration/ -v --env=test

# Test specific connector
pytest tests/unit/connectors/test_google_calendar.py -v
```

## Debugging

### Common Issues

**Bot not responding:**
1. Check Telegram webhook: `curl https://api.telegram.org/bot{TOKEN}/getWebhookInfo`
2. Check logs: `docker-compose logs -f bot`

**OAuth not working:**
1. Check redirect URI matches exactly
2. Check scopes are correct
3. Check token refresh logic

**Voice not transcribing:**
1. Check Whisper API key
2. Check file format (Telegram sends .oga)
3. Check file size limits

## When Adding New Integration

1. Create connector in `api/connectors/{provider}.py`
2. Implement `BaseConnector` + specific interface
3. Add OAuth flow in `web/app/integrations/{provider}/`
4. Add database models if needed
5. Update `docs/ARCHITECTURE.md`
6. Add tests in `tests/unit/connectors/`

## Update This File

After completing major features, run:
```
/update-docs
```
This will update CLAUDE.md, ARCHITECTURE.md, and PROJECT_STATUS.md.
