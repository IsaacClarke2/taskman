# Documentation Links

Актуальные ссылки на документацию всех используемых библиотек и API.

**Важно:** Перед использованием библиотеки проверь последнюю версию на PyPI/npm и прочитай changelog на предмет breaking changes.

---

## Python Libraries

### Web Framework

| Library | Docs | PyPI | GitHub |
|---------|------|------|--------|
| FastAPI | https://fastapi.tiangolo.com/ | https://pypi.org/project/fastapi/ | https://github.com/tiangolo/fastapi |
| Uvicorn | https://www.uvicorn.org/ | https://pypi.org/project/uvicorn/ | https://github.com/encode/uvicorn |
| Pydantic | https://docs.pydantic.dev/ | https://pypi.org/project/pydantic/ | https://github.com/pydantic/pydantic |

### Database

| Library | Docs | PyPI | GitHub |
|---------|------|------|--------|
| SQLAlchemy 2.0 | https://docs.sqlalchemy.org/en/20/ | https://pypi.org/project/sqlalchemy/ | https://github.com/sqlalchemy/sqlalchemy |
| asyncpg | https://magicstack.github.io/asyncpg/ | https://pypi.org/project/asyncpg/ | https://github.com/MagicStack/asyncpg |
| Alembic | https://alembic.sqlalchemy.org/ | https://pypi.org/project/alembic/ | https://github.com/sqlalchemy/alembic |

### Telegram Bot

| Library | Docs | PyPI | GitHub |
|---------|------|------|--------|
| aiogram 3.x | https://docs.aiogram.dev/en/latest/ | https://pypi.org/project/aiogram/ | https://github.com/aiogram/aiogram |

**Важно:** aiogram 3.x имеет breaking changes относительно 2.x. Используй документацию для версии 3.

### AI / OpenAI

| Library | Docs | PyPI |
|---------|------|------|
| openai | https://platform.openai.com/docs/libraries/python-library | https://pypi.org/project/openai/ |

**API Docs:**
- Models Overview: https://platform.openai.com/docs/models
- Responses API (новый): https://platform.openai.com/docs/api-reference/responses
- Chat Completions: https://platform.openai.com/docs/guides/text-generation
- Whisper (Speech-to-Text): https://platform.openai.com/docs/guides/speech-to-text

**Актуальные модели (январь 2026):**
- `gpt-5.2` — flagship, самая умная
- `gpt-5-mini` — рекомендуется для парсинга ($0.25/1M input)
- `gpt-5-nano` — самая дешёвая ($0.05/1M input)
- `whisper-1` — speech-to-text

### Google APIs

| Library | Docs | PyPI |
|---------|------|------|
| google-api-python-client | https://googleapis.github.io/google-api-python-client/docs/ | https://pypi.org/project/google-api-python-client/ |
| google-auth | https://google-auth.readthedocs.io/ | https://pypi.org/project/google-auth/ |
| google-auth-oauthlib | https://google-auth-oauthlib.readthedocs.io/ | https://pypi.org/project/google-auth-oauthlib/ |

**API Docs:**
- Calendar API Reference: https://developers.google.com/calendar/api/v3/reference
- OAuth 2.0 for Web: https://developers.google.com/identity/protocols/oauth2/web-server

### Microsoft / Outlook

| Library | Docs | PyPI |
|---------|------|------|
| msal | https://msal-python.readthedocs.io/ | https://pypi.org/project/msal/ |

**API Docs:**
- Microsoft Graph Calendar: https://learn.microsoft.com/en-us/graph/api/resources/calendar
- Graph API Reference: https://learn.microsoft.com/en-us/graph/api/overview

### CalDAV (Apple Calendar)

| Library | Docs | PyPI |
|---------|------|------|
| caldav | https://caldav.readthedocs.io/ | https://pypi.org/project/caldav/ |

**iCloud CalDAV:**
- Endpoint: `https://caldav.icloud.com`
- Requires app-specific password

### HTTP Client

| Library | Docs | PyPI |
|---------|------|------|
| httpx | https://www.python-httpx.org/ | https://pypi.org/project/httpx/ |

### Background Jobs

| Library | Docs | PyPI |
|---------|------|------|
| arq | https://arq-docs.helpmanual.io/ | https://pypi.org/project/arq/ |
| redis | https://redis-py.readthedocs.io/ | https://pypi.org/project/redis/ |

### Security

| Library | Docs | PyPI |
|---------|------|------|
| cryptography | https://cryptography.io/en/latest/ | https://pypi.org/project/cryptography/ |
| python-jose | https://python-jose.readthedocs.io/ | https://pypi.org/project/python-jose/ |

---

## JavaScript / TypeScript

### Next.js

| Library | Docs | npm |
|---------|------|-----|
| Next.js | https://nextjs.org/docs | https://www.npmjs.com/package/next |
| React | https://react.dev/ | https://www.npmjs.com/package/react |

**Используй App Router** (не Pages Router):
- https://nextjs.org/docs/app

### UI Components (опционально)

| Library | Docs | npm |
|---------|------|-----|
| shadcn/ui | https://ui.shadcn.com/ | (не npm, копируются в проект) |
| Tailwind CSS | https://tailwindcss.com/docs | https://www.npmjs.com/package/tailwindcss |

---

## External APIs

### Notion API

- **Base URL:** `https://api.notion.com/v1`
- **Docs:** https://developers.notion.com/reference/intro
- **Authentication:** https://developers.notion.com/docs/authorization
- **API Version Header:** `Notion-Version: 2022-06-28`

### Telegram Bot API

- **Docs:** https://core.telegram.org/bots/api
- **Login Widget:** https://core.telegram.org/widgets/login
- **Webhook Guide:** https://core.telegram.org/bots/webhooks

### OpenAI API

- **Base URL:** `https://api.openai.com/v1`
- **Docs:** https://platform.openai.com/docs/api-reference
- **Models:** 
  - Text: `gpt-5-mini` (рекомендуется для парсинга), `gpt-5-nano` (ещё дешевле)
  - Speech-to-Text: `whisper-1`

### Google Calendar API

- **Base URL:** `https://www.googleapis.com/calendar/v3`
- **Reference:** https://developers.google.com/calendar/api/v3/reference
- **Scopes:**
  - `https://www.googleapis.com/auth/calendar.events`
  - `https://www.googleapis.com/auth/calendar.readonly`

### Microsoft Graph API

- **Base URL:** `https://graph.microsoft.com/v1.0`
- **Calendar Reference:** https://learn.microsoft.com/en-us/graph/api/resources/calendar
- **Scopes:**
  - `Calendars.ReadWrite`
  - `User.Read`
  - `offline_access`

---

## Docker Images

| Image | Docker Hub |
|-------|------------|
| Python | https://hub.docker.com/_/python (use `python:3.11-slim`) |
| PostgreSQL | https://hub.docker.com/_/postgres (use `postgres:15-alpine`) |
| Redis | https://hub.docker.com/_/redis (use `redis:7-alpine`) |
| Node.js | https://hub.docker.com/_/node (use `node:20-alpine`) |

---

## Как проверять актуальность

1. **PyPI:** Открой страницу пакета, посмотри "Release history"
2. **npm:** `npm view {package} version`
3. **GitHub:** Проверь Releases и CHANGELOG.md
4. **API Docs:** Большинство API имеют версионирование в URL или headers

---

## Если документация устарела

1. Проверь GitHub Issues — там часто обсуждают проблемы
2. Посмотри примеры в репозитории библиотеки (`/examples`)
3. Проверь Stack Overflow с фильтром по дате
4. Для API — используй официальные SDK, они обычно актуальнее raw HTTP примеров
